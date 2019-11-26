
import argparse
import getpass
import ssl

import libs.vsanmgmtObjects
from libs.vsanclustercheck import VsanClusterCheck


def get_args():
    """ Supports the command-line arguments listed below. """
    parser = argparse.ArgumentParser(description='Process args for vSAN SDK sample application')
    parser.add_argument('-s', '--host', required=True, action='store', help='Remote host to connect to')
    parser.add_argument('-o', '--port', type=int, default=443, action='store', help='Port to connect on')
    parser.add_argument('-u', '--user', required=True, action='store', help='Username when connecting to host')
    parser.add_argument('-p', '--password', required=False, action='store', help='Password when connecting to host')
    parser.add_argument('--cluster', dest='cluster_name', metavar="CLUSTER", default='VSAN-Cluster')
    args = parser.parse_args()
    return args


def main():
    args = get_args()
    if args.password:
        password = args.password
    else:
        password = getpass.getpass(prompt='Enter password for host %s and user %s: ' % (args.host, args.user))

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    vcc = VsanClusterCheck(host=args.host,
                           user=args.user,
                           password=password,
                           port=int(args.port),
                           cluster=args.cluster_name,
                           context=context)

    vcc.get_cluster_vsan_capacity()
    vcc.get_health_status()
    vcc.get_cluster_hcl_info()


if __name__ == "__main__":
    main()
