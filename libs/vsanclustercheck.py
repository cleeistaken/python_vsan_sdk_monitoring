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
__author__ = 'VMware, Inc'

import ssl

from libs import vsanapiutils

from operator import attrgetter
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
from typing import List

from libs.util import convert_bytes, print_green, print_yellow, print_red, print_yes_no, print_no_yes, \
    print_thresholds_inc, print_thresholds_dec


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

        if not self.si:
            raise ValueError('Could not connect to the specified host using specified username and password')

        # To avoid multiple code warnings about private member access
        # noinspection PyProtectedMember
        self.si_stub = self.si._stub

        # Detecting version
        self.about_info = self.si.content.about
        if int(self.about_info.apiVersion.split('.')[0]) < 6:
            raise ValueError('Host version {} (lower than 6.0) is not supported.'.format(self.about_info.apiVersion))

        # Get VMODL API version
        self.api_version = vsanapiutils.GetLatestVmodlVersion(self.host_name)

        # Check if host is VirtualCenter
        # Note: This sample only assumes connection to vCenter instances
        if self.about_info.apiType != 'VirtualCenter':
            raise ValueError('Host {} is not a VirtualCenter.'.format(self.host_name))

        # Get cluster
        # Note: This sample assumes a single cluster is specified.
        self.cluster_instance = self.__get_cluster_instance()

        if self.cluster_instance is None:
            raise ValueError('Cluster {} is not found for {}.'.format(self.cluster_instance, self.host_name))

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

    def __get_cluster_vms(self) -> List[vim.VirtualMachine]:
        vms: List[vim.VirtualMachine] = []
        content = self.si.RetrieveContent()
        for cluster_obj in self.__get_obj(content, vim.ComputeResource):
            if self.cluster_name:
                if cluster_obj.name == self.cluster_name:
                    for host in sorted(cluster_obj.host, key=attrgetter('name')):
                        vms.extend(host.vm)
        return vms

    @classmethod
    def __get_obj(cls, content, vimtype):
        return [item for item in content.viewManager.CreateContainerView(content.rootFolder,
                                                                         [vimtype],
                                                                         recursive=True).view]

    @classmethod
    def __color_cluster_status(cls, value: str) -> str:
        if value is None:
            return 'no status'
        elif value == 'green':
            return print_green(value)
        elif value == 'red':
            return print_red(value)
        elif value == 'yellow':
            return print_yellow(value)
        else:
            return print_red('unknown status: {}}'.format(value))

    @classmethod
    def __color_clomd_status(cls, value: str) -> str:
        if value is None:
            return 'no status'
        elif value == 'alive':
            return print_green(value)
        elif value == 'abnormal':
            return print_red(value)
        elif value == 'unknown':
            return print_yellow(value)
        else:
            return print_red('unknown status: {}}'.format(value))

    @classmethod
    def __color_obj_health_status(cls, value: str) -> str:
        """ docs/vim.host.VsanObjectHealth.VsanObjectHealthState.html """
        if value is None:
            return 'no status'
        if value in ['datamove', 'healthy']:
            return print_green(value)
        elif value in ['nonavailabilityrelatedincompliance',
                       'nonavailabilityrelatedincompliancewithpausedrebuild',
                       'nonavailabilityrelatedincompliancewithpolicypending',
                       'nonavailabilityrelatedreconfig',
                       'reducedavailabilitywithactiverebuild',
                       'reducedavailabilitywithnorebuild',
                       'reducedavailabilitywithpolicypending',
                       'reducedavailabilitywithnorebuilddelaytimer']:
            return print_yellow(value)
        elif value in ['inaccessible',
                       'nonavailabilityrelatedincompliance',
                       'reducedavailabilitywithpausedrebuild',
                       'reducedavailabilitywithpolicypendingfailed'
                       'VsanObjectHealthState_Unknown']:
            return print_red(value)
        else:
            return print_red('unknown status: {}]'.format(value))

    @classmethod
    def __color_obj_compliance_status(cls, value: str) -> str:
        if value is None:
            return 'no status'
        elif value == 'compliant':
            return print_green(value)
        elif value == 'nonCompliant':
            return print_red(value)
        elif value == 'notApplicable':
            return value
        else:
            return print_red('unknown status: {}}'.format(value))

    @classmethod
    def ___truncate_vm_name(cls, value, length: int = 30) -> str:
        if len(value) <= length:
            return '{}'.format(value)
        else:
            return '{}...'.format(value[0:(length - 3)])

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

        print('\nvSAN capacity on host {}\n'.format(self.host_name),
              ' Cluster: {}\n'.format(self.cluster_name))

        # Capacity values
        capacity_total = capacity_data.totalCapacityB
        capacity_free = capacity_data.freeCapacityB
        capacity_free_pct = (capacity_free / capacity_total) * 100
        capacity_used = capacity_total - capacity_free
        capacity_used_pct = (capacity_used / capacity_total) * 100
        capacity_committed = capacity_data.uncommittedB
        capacity_committed_pct = (capacity_committed / capacity_total) * 100

        # Print capacity values
        print('Summary\n',
              ' Total Capacity:     {:>10}\n'.format(convert_bytes(capacity_total)),
              ' Free Capacity:      {:>10} ({})\n'.format(convert_bytes(capacity_free),
                                                          print_thresholds_dec(capacity_free_pct)),
              ' Used Capacity:      {:>10} ({})\n'.format(convert_bytes(capacity_used),
                                                          print_thresholds_inc(capacity_used_pct)),
              ' Committed Capacity: {:>10} ({})\n'.format(convert_bytes(capacity_committed),
                                                          print_thresholds_inc(capacity_committed_pct)))

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
                  ' Metadata size: {:>10}\n'.format(convert_bytes(efficiency_metadata)),
                  ' Logical size:  {:>10}\n'.format(convert_bytes(efficiency_logical)),
                  ' Logical used:  {:>10} ({})\n'.format(convert_bytes(efficiency_logical_used),
                                                         print_thresholds_inc(efficiency_logical_used_pct)),
                  ' Physical size: {:>10}\n'.format(convert_bytes(efficiency_physical)),
                  ' Physical used: {:>10} ({})\n'.format(convert_bytes(efficiency_physical_used),
                                                         print_thresholds_inc(efficiency_physical_used_pct)))

        # Space usage details
        print('Space usage details')
        for obj in sorted(capacity_data.spaceDetail.spaceUsageByObjectType, key=attrgetter('objType')):
            print('  Type: {:<19}'.format(obj.objType),
                  'Used: {:>10}'.format(convert_bytes(obj.usedB)),
                  'Reserved: {:>10}'.format(convert_bytes(obj.reservedCapacityB)),
                  'Overhead: {:>10}'.format(convert_bytes(obj.overheadB)),
                  'Thick: {:>10}'.format(convert_bytes(obj.overReservedB)))

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
        fields = ['timestamp', 'clusterStatus', 'clomdLiveness', 'diskBalance', 'perfsvcHealth', 'groups']

        # vSAN cluster health summary can be cached at vCenter.
        health_data = vhs.VsanQueryVcClusterHealthSummary(cluster=self.cluster_instance,
                                                          includeObjUuids=True,
                                                          fields=fields,
                                                          fetchFromCache=fetch_from_cache)

        print('\nvSAN health status on host {}\n'.format(self.host_name),
              ' Cluster: {}\n'.format(self.cluster_name),
              ' Using cached data?: {}\n'.format('Yes' if fetch_from_cache else 'No'),
              ' Timestamp: {}'.format(health_data.timestamp))

        if health_data.clusterStatus:
            cluster_status = health_data.clusterStatus
            print('\nCluster: {:<31} Status: {}\n\nHosts'.format(self.cluster_name,
                                                                 self.__color_cluster_status(cluster_status.status)))
            for host_status in sorted(cluster_status.trackedHostsStatus, key=attrgetter('hostname')):
                print('  Host: {:<32} Status: {}'.format(host_status.hostname,
                                                         self.__color_cluster_status(host_status.status)))

        if health_data.clomdLiveness:
            clomd_liveness = health_data.clomdLiveness
            print('\nCLOMD Liveness Issues: {}'.format(print_no_yes(clomd_liveness.issueFound)))
            for host in sorted(clomd_liveness.clomdLivenessResult, key=attrgetter('hostname')):
                print('  Host: {:<32} Status: {}'.format(host.hostname, self.__color_clomd_status(host.clomdStat)))

        if health_data.diskBalance:
            disk_balance = health_data.diskBalance
            print('\nDisk Balance')
            for disk in sorted(disk_balance.disks, key=attrgetter('uuid')):
                print('  UUID: {:<37} Usage: {:>3}% Variance {:>3}%'.format(disk.uuid.ljust(37),
                                                                            disk.fullness,
                                                                            disk.variance))

        if health_data.perfsvcHealth:
            perf_svc_health = health_data.perfsvcHealth
            print('\nPerformance Service\n',
                  '  Enough Free Space: {}\n'.format(print_yes_no(perf_svc_health.enoughFreeSpace)),
                  '  Stats Objects Consistent: {}\n'.format(print_yes_no(perf_svc_health.statsObjectConsistent)),
                  '  Verbose Mode: {}'.format(print_no_yes(perf_svc_health.verboseModeStatus)))

    def get_cluster_hcl_info(self, fetch_from_cache: bool = False) -> None:
        """ Get the hardware HCL status for the cluster

        Managed Object: VsanVcClusterGetHclInfo
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanVcClusterHealthSystem.html#getClusterHclInfo

        Data Object: VsanClusterHclInfo
        https://vdc-download.vmware.com/vmwb-repository/dcr-public/8ed923df-bad4-49b3-b677-45bca5326e85/d2d90bb6-d1b3-4266-8ce5-443680187a9a/vim.cluster.VsanClusterHclInfo.html
        """

        # Get vSAN health system from the vCenter Managed Object references.
        vhs = self.vc_mos['vsan-cluster-health-system']
        fields = ['timestamp', 'hclInfo']

        health_data = vhs.VsanQueryVcClusterHealthSummary(cluster=self.cluster_instance,
                                                          includeObjUuids=True,
                                                          fields=fields,
                                                          fetchFromCache=fetch_from_cache)
        hcl_info = health_data.hclInfo

        print('\nvSAN HCL status on host {}\n'.format(self.host_name),
              ' Cluster: {}\n'.format(self.cluster_name),
              ' Using cached data?: {}\n'.format('Yes' if fetch_from_cache else 'No'),
              ' Timestamp: {}\n'.format(health_data.timestamp),
              ' HCL DB Age: {} (updated {})'.format(hcl_info.hclDbAgeHealth, hcl_info.hclDbLastUpdate))

        for host in sorted(hcl_info.hostResults, key=attrgetter('hostname')):
            print('\nChecking Host {} ({})'.format(host.hostname, host.releaseName))

            print('Controllers')
            for device in host.controllers:
                print('  Device:          {}\n'.format(device.deviceName),
                      '   Name:           {}\n'.format(device.deviceDisplayName),
                      '   Used by vSAN:   {}\n'.format(device.usedByVsan),
                      '   Supported?:     {}\n'.format(print_yes_no(device.deviceOnHcl)),
                      '   Driver:         {}\n'.format(device.driverName),
                      '     Version:      {}\n'.format(device.driverVersion),
                      '     Supported?:   {}\n'.format(print_yes_no(device.driverVersionSupported)),
                      '     HCL versions: {}\n'.format(', '.join(device.driverVersionsOnHcl)),
                      '   Firmware\n',
                      '     Version:      {}\n'.format(device.fwVersion),
                      '     Supported?:   {}\n'.format(print_yes_no(device.fwVersionSupported)),
                      '     HCL versions: {}\n'.format(', '.join(device.fwVersionOnHcl)),
                      '   Tool:           {}\n'.format(device.toolName),
                      '     Version:      {}\n'.format(device.toolVersion),
                      '     Supported?:   {}\n'.format(print_yes_no(device.fwVersionSupported)),
                      '     HCL versions: {}'.format(', '.join(device.fwVersionOnHcl)))

    def get_cluster_vms(self) -> None:
        """ Get all VMs in the cluster with storage on vSAN

        https://github.com/vmware/pyvmomi-community-samples/blob/master/samples/getvmsbycluster.py
        https://github.com/vmware/pyvmomi-community-samples/issues/253
        https://stackoverflow.com/questions/38666195/getting-an-instances-actual-used-allocated-disk-space-in-vmware-with-pyvmomi/38868247#38868247
        """

        vcos = self.vc_mos['vsan-cluster-object-system']

        cos_data = vcos.VsanQueryObjectIdentities(cluster=self.cluster_instance,
                                                  includeHealth=True,
                                                  includeObjIdentity=True)

        cos_health = cos_data.health.objectHealthDetail
        print('\nvSAN object health status on host {}\n'.format(self.host_name),
              ' Cluster: {}\n'.format(self.cluster_name),
              ' Objects: {}\n'.format(sum([x.numObjects for x in cos_health])),
              ' Health:  {}'.format(','.join([self.__color_obj_health_status(x.health) for x in cos_health])))

        cos_uuids = [vim.cluster.VsanObjectQuerySpec(uuid=x.uuid) for x in cos_data.identities]
        cos_objs_info = vcos.VosQueryVsanObjectInformation(cluster=self.cluster_instance,
                                                           vsanObjectQuerySpecs=cos_uuids)

        vms = self.__get_cluster_vms()

        # Build a list of tuples where we pair the identity and the information to
        # make it easier to print and return.
        # The objs tuple could be returned or further processed.
        # the print_objs is created to make the sorting and printing much faster than
        # working directly with the (large) objs structure.
        objs = []
        print_objs = []
        for obj_ident in cos_data.identities:
            obj_ident.vm = next((vm for vm in vms if obj_ident.vm == vm), None)
            obj_info = next((item for item in cos_objs_info if item.vsanObjectUuid == obj_ident.uuid), None)
            objs.append((obj_ident, obj_info))

            # Populate the print_data
            vm_name = self.___truncate_vm_name(obj_ident.vm.name if obj_ident.vm else '')
            obj_type = obj_ident.type
            obj_uuid = obj_ident.uuid
            obj_health = self.__color_obj_health_status(obj_info.vsanHealth)
            obj_compliance = self.__color_obj_compliance_status(obj_info.spbmComplianceResult.complianceStatus)
            print_objs.append((vm_name,
                               obj_type,
                               obj_uuid,
                               obj_health,
                               obj_compliance))

        print('\nvSAN objects')
        for vm_name, obj_type, obj_uuid, obj_health, obj_compliance in sorted(print_objs, key=lambda x: [x[0], x[1]]):
            print('  VM: {:31}'.format(vm_name),
                  'Type: {:20}'.format(obj_type),
                  'UUID: {}'.format(obj_uuid),
                  'Status: {}'.format(obj_health),
                  'Policy: {}'.format(obj_compliance))

    def get_cluster_network_performance_history(self):
        # VsanQueryVcClusterNetworkPerfHistoryTest
        pass

    def get_cluster_vmk_load_history(self):
        # VsanQueryVcClusterVmdkLoadHistoryTest
        pass

    def __del__(self):
        Disconnect(self.si)
