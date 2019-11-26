#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright 2019 VMware, Inc.  All rights reserved.

This file includes sample codes for vCenter and ESXi sides vSAN API accessing.

To provide an example of vCenter side vSAN API access, it shows how to get vSAN
cluster health status by invoking the QueryClusterHealthSummary() API of the
VsanVcClusterHealthSystem MO.

To provide an example of ESXi side vSAN API access, it shows how to get
performance server related host information by invoking the
VsanPerfQueryNodeInformation() API of the VsanPerformanceManager MO.

Ref.
https://storagehub.vmware.com/t/vmware-vsan/vsan-6-2-2-node-for-remote-and-branch-office-deployment/typical-api-usage-for-vsan-cluster-deployment/

"""
from operator import attrgetter

from libs.util import convert_bytes, print_green, print_yellow, print_red, print_yes_no, print_no_yes, \
    print_thresholds_inc, print_thresholds_dec

__author__ = 'VMware, Inc'

import ssl

from libs import vsanapiutils

from pyVim.connect import SmartConnect, Disconnect


class VsanClusterCheck(object):

    def __init__(self,
                 host: str,
                 user: str,
                 password: str,
                 port: int,
                 cluster: str,
                 context: ssl.SSLContext):
        self.host_name = host
        self.ssl_context = context
        self.cluster_name = cluster
        self.si = SmartConnect(host=host,
                               user=user,
                               pwd=password,
                               port=int(port),
                               sslContext=context)

        # To avoid multiple code warnings about private member access
        # noinspection PyProtectedMember
        self.si_stub = self.si._stub

        # Detecting version
        self.about_info = self.si.content.about
        if int(self.about_info.apiVersion.split('.')[0]) < 6:
            raise ValueError('The host version %s (lower than 6.0) is not supported.' % self.about_info.apiVersion)

        # Get VMODL API version
        self.api_version = vsanapiutils.GetLatestVmodlVersion(self.host_name)

        # Check if host is VirtualCenter
        # Note: This sample only assumes connection to vCenter instances
        if self.about_info.apiType != 'VirtualCenter':
            raise ValueError('Host %s is not a VirtualCenter.' % self.host_name)

        # Get cluster
        # Note: This sample assumes a single cluster is specified.
        self.cluster_instance = self.__get_cluster_instance()

        if self.cluster_instance is None:
            raise ValueError('Cluster %s is not found for %s.' % (self.cluster_instance, self.host_name))

        # Get vCenter Managed Object references.
        self.vc_mos = vsanapiutils.GetVsanVcMos(self.si_stub,
                                                context=self.ssl_context,
                                                version=self.api_version)

    def __get_cluster_instance(self):
        content = self.si.RetrieveContent()
        search_index = content.searchIndex
        datacenters = content.rootFolder.childEntity
        for datacenter in datacenters:
            cluster = search_index.FindChild(datacenter.hostFolder, self.cluster_name)
            if cluster is not None:
                return cluster
        return None

    @classmethod
    def __print_cluster_status(cls, value: str) -> str:
        if value is None:
            return 'No status'
        elif value == 'green':
            return print_green('Green')
        elif value == 'red':
            return print_red('Red')
        elif value == 'yellow':
            return print_yellow('Yellow')
        else:
            return value

    @classmethod
    def __print_clomd_status(cls, value: str) -> str:
        if value is None:
            return 'No status'
        elif value == 'alive':
            return print_green('Alive')
        elif value == 'abnormal':
            return print_red('Abnormal')
        elif value == 'unknown':
            return print_yellow('Unknown')
        else:
            return value

    def get_cluster_vsan_capacity(self) -> None:
        """Get the cluster vSAN capacity and usage

        API Reference:

        Managed Object: VsanQuerySpaceUsage
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanSpaceReportSystem.html

        Data Object: VsanSpaceUsage
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanSpaceUsage.html

        Data Object: VsanSpaceUsageDetailResult
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanSpaceUsageDetailResult.html

        Data Object: VsanSpaceUsageDetailResult
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanObjectSpaceSummary.html

        Data Object - VimVsanDataEfficiencyCapacityState
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.vsan.DataEfficiencyCapacityState.html
        """

        # Get vSAN Cluster Space Report System
        vsrs = self.vc_mos['vsan-cluster-space-report-system']
        capacity_data = vsrs.VsanQuerySpaceUsage(cluster=self.cluster_instance)

        print('\nvSAN capacity on host %s\n' % self.host_name,
              ' Cluster: %s\n' % self.cluster_name)

        # Capacity values
        capacity_total = capacity_data.totalCapacityB
        capacity_free = capacity_data.freeCapacityB
        capacity_free_pct = (capacity_free / capacity_total) * 100
        capacity_used = capacity_total - capacity_free
        capacity_used_pct = (capacity_used / capacity_total) * 100
        capacity_committed = capacity_data.uncommittedB
        capacity_committed_pct = (capacity_committed / capacity_total) * 100

        # Print capacity values
        print("Summary\n",
              " Total Capacity:     %s\n" % convert_bytes(capacity_total).rjust(10),
              " Free Capacity:      %s (%s)\n" % (convert_bytes(capacity_free).rjust(10),
                                                  print_thresholds_dec(capacity_free_pct)),
              " Used Capacity:      %s (%s)\n" % (convert_bytes(capacity_used).rjust(10),
                                                  print_thresholds_inc(capacity_used_pct)),
              " Committed Capacity: %s (%s)\n" % (convert_bytes(capacity_committed).rjust(10),
                                                  print_thresholds_inc(capacity_committed_pct)),
              )

        # Dedupe and Compression
        if not capacity_data.efficientCapacity:
            print('Data Efficiency: Not Enabled\n')
        else:
            ec = capacity_data.efficientCapacity

            # Data efficiency values
            efficiency_metadata = ec.dedupMetadataSize
            efficiency_logical = ec.logicalCapacity
            efficiency_logical_used = ec.logicalCapacityUsed
            efficiency_logical_used_pct = (efficiency_logical_used / efficiency_logical) * 100
            efficiency_physical = ec.physicalCapacity
            efficiency_physical_used = ec.physicalCapacityUsed
            efficiency_physical_used_pct = (efficiency_physical_used / efficiency_physical) * 100

            print('Data Efficiency: Enabled\n',
                  ' Metadata size: %s\n' % convert_bytes(efficiency_metadata).rjust(10),
                  ' Logical size:  %s\n' % convert_bytes(efficiency_logical).rjust(10),
                  ' Logical used:  %s (%s)\n' % (convert_bytes(efficiency_logical_used).rjust(10),
                                                 print_thresholds_inc(efficiency_logical_used_pct)),
                  ' Physical size: %s\n' % convert_bytes(efficiency_physical).rjust(10),
                  ' Physical used: %s (%s)\n' % (convert_bytes(efficiency_physical_used).rjust(10),
                                                 print_thresholds_inc(efficiency_physical_used_pct)),
                  )

        # Space usage details
        print("Space usage details")
        for obj in sorted(capacity_data.spaceDetail.spaceUsageByObjectType, key=attrgetter('objType')):
            print('  Type: %s' % obj.objType.ljust(19),
                  'Used: %s' % convert_bytes(obj.usedB).rjust(10),
                  'Reserved: %s' % convert_bytes(obj.reservedCapacityB).rjust(10),
                  'Overhead: %s' % convert_bytes(obj.overheadB).rjust(10),
                  'Thick: %s' % convert_bytes(obj.overReservedB).rjust(10)
                  )

    def get_health_status(self, fetch_from_cache: bool = False) -> None:
        """Get the cluster vSAN health status

        Managed Object: VsanQueryVcClusterHealthSummary
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanVcClusterHealthSystem.html#queryClusterHealthSummary

        Data Object: VsanClusterHealthSummary
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanClusterHealthSummary.html

        Data Object: VsanClusterClomdLivenessResult
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanClusterClomdLivenessResult.html

        Data Object: VsanClusterBalanceSummary
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanClusterBalanceSummary.html

        Data Object: VsanClusterBalanceSummary
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanClusterBalancePerDiskInfo.html

        Data Object: VsanPerfsvcHealthResult
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.vsan.VsanPerfsvcHealthResult.html

        Data Object: VsanPerfNodeInformation
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanPerfNodeInformation.html
        """

        # Get vSAN Cluster Health System
        vhs = self.vc_mos['vsan-cluster-health-system']
        fields = ['timestamp', 'clusterStatus',  'clomdLiveness', 'diskBalance', 'perfsvcHealth', 'groups']

        # vSAN cluster health summary can be cached at vCenter.
        health_data = vhs.VsanQueryVcClusterHealthSummary(cluster=self.cluster_instance,
                                                          includeObjUuids=True,
                                                          fields=fields,
                                                          fetchFromCache=fetch_from_cache)

        print('\nvSAN health status on host %s\n' % self.host_name,
              ' Cluster: %s\n' % self.cluster_name,
              ' Using cached data?: %s\n' % ('Yes' if fetch_from_cache else 'No'),
              ' Timestamp: %s' % health_data.timestamp)

        if health_data.clusterStatus:
            cluster_status = health_data.clusterStatus
            print('\nCluster: %s Status: %s \n\nHosts' % (self.cluster_name.ljust(31),
                                                          self.__print_cluster_status(cluster_status.status)))
            for host_status in sorted(cluster_status.trackedHostsStatus, key=attrgetter('hostname')):
                print('  Host: %s Status: %s' % (host_status.hostname.ljust(32),
                                                 self.__print_cluster_status(host_status.status)))

        if health_data.clomdLiveness:
            clomd_liveness = health_data.clomdLiveness
            print('\nCLOMD Liveness Issues: %s' % print_no_yes(clomd_liveness.issueFound))
            for host in sorted(clomd_liveness.clomdLivenessResult, key=attrgetter('hostname')):
                print('  Host: %s Status: %s' % (host.hostname.ljust(32), self.__print_clomd_status(host.clomdStat)))

        if health_data.diskBalance:
            disk_balance = health_data.diskBalance
            print('\nDisk Balance')
            for disk in sorted(disk_balance.disks, key=attrgetter('uuid')):
                print('  UUID: %s Usage: %3d%% Variance %3d%%' % (disk.uuid.ljust(37),
                                                                  disk.fullness,
                                                                  disk.variance))

        if health_data.perfsvcHealth:
            perf_svc_health = health_data.perfsvcHealth
            print('\nPerformance Service\n',
                  '  Enough Free Space: %s\n' % print_yes_no(perf_svc_health.enoughFreeSpace),
                  '  Stats Objects Consistent: %s\n' % print_yes_no(perf_svc_health.statsObjectConsistent),
                  '  Verbose Mode: %s' % print_no_yes(perf_svc_health.verboseModeStatus))

    def get_cluster_hcl_info(self, fetch_from_cache: bool = False) -> None:
        """

        Managed Object: VsanVcClusterGetHclInfo
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanVcClusterHealthSystem.html#getClusterHclInfo

        Data Object: VsanClusterHclInfo
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanClusterHclInfo.html
        """
        # VsanVcClusterGetHclInfo

        # Get vSAN health system from the vCenter Managed Object references.
        vhs = self.vc_mos['vsan-cluster-health-system']
        fields = ['timestamp', 'hclInfo']

        health_data = vhs.VsanQueryVcClusterHealthSummary(cluster=self.cluster_instance,
                                                          includeObjUuids=True,
                                                          fields=fields,
                                                          fetchFromCache=fetch_from_cache)
        hcl_info = health_data.hclInfo

        print('\nvSAN HCL status on host %s\n' % self.host_name,
              ' Cluster: %s\n' % self.cluster_name,
              ' Using cached data?: %s\n' % ('Yes' if fetch_from_cache else 'No'),
              ' Timestamp: %s\n' % health_data.timestamp,
              ' HCL DB Age: %s (updated %s)' % (hcl_info.hclDbAgeHealth, hcl_info.hclDbLastUpdate))

        for host in sorted(hcl_info.hostResults, key=attrgetter('hostname')):
            print("\nChecking Host %s (%s)" % (host.hostname, host.releaseName))

            print('Controllers')
            for device in host.controllers:
                print('  Device:          %s\n' % device.deviceName,
                      '   Name:           %s\n' % device.deviceDisplayName,
                      '   Used by vSAN:   %s\n' % device.usedByVsan,
                      '   Supported?:     %s\n' % print_yes_no(device.deviceOnHcl),
                      '   Driver:         %s\n' % device.driverName,
                      '     Version:      %s\n' % device.driverVersion,
                      '     Supported?:   %s\n' % print_yes_no(device.driverVersionSupported),
                      '     HCL versions: %s\n' % ', '.join(device.driverVersionsOnHcl),
                      '   Firmware\n',
                      '     Version:      %s\n' % device.fwVersion,
                      '     Supported?:   %s\n' % print_yes_no(device.fwVersionSupported),
                      '     HCL versions: %s\n' % ', '.join(device.fwVersionOnHcl),
                      '   Tool:           %s\n' % device.toolName,
                      '     Version:      %s\n' % device.toolVersion,
                      '     Supported?:   %s\n' % print_yes_no(device.fwVersionSupported),
                      '     HCL versions: %s' % ', '.join(device.fwVersionOnHcl))

    def get_cluster_vms(self):
        pass

    def get_cluster_network_performance_history(self):
        # VsanQueryVcClusterNetworkPerfHistoryTest
        pass

    def get_cluster_vmk_load_history(self):
        # VsanQueryVcClusterVmdkLoadHistoryTest
        pass

    def __del__(self):
        Disconnect(self.si)
