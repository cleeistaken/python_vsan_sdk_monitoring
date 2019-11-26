# python_vsan_sdk_example
Sample code showing how to use the vSAN SDK to query vSAN status and health metrics.  


## Requirements
This code was developed and tested with the following versions

### Interpreter
* Python 3.7.5

### Modules
* certifi 2019.9.11	
* cffi 1.13.2	
* chardet 3.0.4	
* colored 1.4.0
* cryptography 2.8
* idna 2.8
* pip 19.3.1
* prompt-toolkit 2.0.10
* pyOpenSSL 19.1.0
* pycparser 2.19
* pyflakes 2.1.1
* pyvmomi 6.7.3
* requests 2.22.0
* setuptools 41.6.0
* six 1.13.0
* urllib3 1.25.7
* wcwidth 0.1.7


## Usage:

```shell script
python3.7 queryvsancluster.py \
  -s <vcenter ip or hostname> \
  -u <username>               \
  -p <password>               \
  --cluster <cluster name>
```


## Versions
### 0.1 Initial release
Note: This code assumes the target is a vCenter and the cluster has vSAN enabled. It was tested against vSphere 6.7U3 environments but may have issues with older versions because the code assumes a 6.7U3 API and this API has few properties and methods not found in earlier versions. We will handle these cases in later releases. 
* Storage capacity and disk utilization
* Cluster and host health
* Storage controller HCL status



## References
vSAN Management API 6.7U3
https://code.vmware.com/apis/693/vsan 