# RemoteSingularitySpawner
**RemoteSingularitySpawner** enables [JupyterHub](https://github.com/jupyterhub/jupyterhub) to spawn single user notebook serves in Singularity containers on remote host specified by user.
## Technical overview
**RemoteSingularitySpawner** uses SSH (provided by [paramiko](http://www.paramiko.org/)) to login remote host and spawn single user notebook servers. Meanwhile, it uses `kill` command to check the status of notebook servers and control this process. Of course, the users must have SSH key for automating logins to let RemoteSingularitySpawner login remote host without password. Currently, this package supports RSA key only, but you can modifty the source code to support other keys.
## How to use
### 1. Install Singularity
[Singularity](https://sylabs.io/docs/) must be installed on all hosts you want to run jupyterhub and notebook servers. Please refer the official documents: https://sylabs.io/docs/
### 2. Build a Singularity Container
Build a Singularity container needs a Singularity Definition File (or “def file” for short). I have provided a def file (actually, the container used in my cluster is defined by this file) in this repository as an example. In this def file, I have included openssh-server(necessary for paramiko to work), jupyterhub, jupyter notebook, jupyterlab, python 2.7.15rc1, python 3.6.5, R 3.6.3, ipython kernel(python 2.7.15 and python 3.6.5), and R kernel(R 3.6.3) for jupyter. Besides, I have installed timezone, vim and iputils-ping for debugging. You can generate your own def file base on this example.  
Run this command to build a Singularity container:
```bash
sudo singularity build jupyterhub.sif jupyterhub.def
```
The command requires sudo just as installing software on your local machine requires root privileges. If you don't have sudo privilege, you can build the container on any machine you can sudo(your own laptop may be a good choice), then copy the image file `jupyterhub.sif` to your cluster. Please refer the Singularity's offical documents in detail.
### 3. Configuration
The jupyterhub in the container use the configuration file outside the container. It's very convenient, because you don't need to rebuild the container every time you have changed the configuration file.  
Run this command to generate a configuration file in the current working directory:
```bash
singularity exec jupyterhub.sif jupyterhub --generate-config
```
Below are some important configurations to let this packge work normally.
```
c.JupyterHub.hub_ip = 'ip_address'
```
The ip address for the Hub process to *bind* to. The notebook server will be spawned on remote hosts, the Hub process must bind to a 'public ip', which means other hosts can connect to the Hub use this ip.
```
c.JupyterHub.spawner_class = 'remote-singularity-spawner'
```
Select the spawner `remote-singularity-spawner` instead of the defualt spawner `LocalProcessSpawner`.
```
c.RemoteSingularitySpawner.singularity_exe_path = 'path_to_singulartiy_exe_file'
```
You can use this to specifity where the Singularity binary file locates. Default value is 'singularity'.
```
c.RemoteSingularitySpawner.singularity_container_path = 'path_to_container'
```
This specifies the path of the container(or image file for accuracy) you want to use. Every host run the jupyterhub and notebook server should access to the container. You can copy the container to every host or put it on shared file systems.
```
c.RemoteSingularitySpawner.nodelist = "host1:host2"
```
The host list you want to spawn notebook server. The formats of the value are: `"hostname1:ip_address1,hostname2:ip_address2"`, `"hostname1:,hostname2:"`, `":ip_address1,:ip_address2"` and `"hostname1:,:ip_address2,hostname3:ip_address3"`. When users launch their server, they will be redirected to a webiste page. In this page, the hostname or ip address(if hostname is omitted) will be shown in a select list, so the users can select a host to spawn notebook server. I have used the python packages [socket](https://docs.python.org/3/library/socket.html) and [ipaddress](https://docs.python.org/3/library/ipaddress.html) to check the validity of the hostname and ip address. Any invalid record will be ignored. If you have provided both the hostname and the ip address for a record, only the validity of ip address will be checked. That means you can name the ip address. Please note that the first valid record will be the default value of the select list.
```
c.RemoteSingularitySpawner.home_path = "path_to_home"
```
The place where all users home directories are created. Default value is `/home`. Some clusters may use other place, so I add this configuration.
```
c.Spawner.default_url = '/lab'
```
This configuration is optional. `'/lab'` means jupyterlab will be used. You can comment this line to use jupyter notebook. By the way, in this configuration, users can still access the classic Notebook at /tree, by either typing that URL into the browser, or by using the “Launch Classic Notebook” item in JupyterLab’s Help menu.
```
c.RemoteSingularitySpawner.default_bind_path = '/path1;/path2'
```
This configuration is optional. When spawn notebook server on remote hosts, `/path1` and `/path2` will be binded into container. Note that Singularity have its own system default bind points(https://sylabs.io/guides/3.5/user-guide/bind_paths_and_mounts.html). By the way, when spawn a notebook server, users will be redirected to a page where users can bind their own path.
### 4. Run the JupyterHub server
```bash
sudo SINGULARITY_BIND="<path_to_home>" singularity run jupyterhub.sif
```
This command will run the image file `jupyterhub.sif` and print all output in the current terminal. It's very userful for debugging. The `path_to_home` should have the same value as the configuration `c.RemoteSingularitySpawner.home_path`. The home path must be binded into container manually, because Singularity will not bind this path automatically for you and the spawner should access to users' key when login remote hosts. The output of notebook server will be saved in the log file `/tmp/jupytersingler_<username>.log` on remote host. Please remember that the configration files of jupyter (in `~/.jupyter` if have) will be used when spawn the notebook server, so don't forget to check those configuration files if the notebook server behave strangely. You can turn this behavior off in jupyterhub configuration file.
When everything is ok, you can run this command to run the container as a service:
```bash
sudo SINGULARITY_BIND="<path_to_home>" singularity instance start jupyterhub.sif jupyterhub_web
```
The log files can be found in the direcotry `/root/.singularity/instances/logs/<hostname>/root`. Then you can use this command to check the status of the instance you just start:
```bash
singularity instance list
```
And use this command to stop instance:
```bash
singularity instance stop jupyterhub_web
```
## FAQ
### 1. Can I use this package if I use LDAP in my cluster?
Of course you can. Actually, I use LDAP in my cluster too.
### 2. Why use Singularity instead of Docker?
In fact, I considered the Docker at first when I developed this package. Docker is complex, and you have to configure network, proxy, LDAP, etc. in your container. But that is ok, I have solved those problems. Then I started to test my package and found a series problem. I couldn't give every user the privilege to run docker, because he is root in the container and can mount path in host machine to do some dangerous work. If I let root to run container for every user on remote machine, login without password became a problem. So I choosed Singularity finally. Singularity is easy and safe to use, and I don't need to configure network, proxy, LDAP, etc in container.
### 3. How can I switch host if I have had a running notebook server?
You have to stop notebook server before you switch host. Logout will not stop the notebook server, and you will be redirected to the previous notebook server when you login again. Using `File -> Hub Control Panel -> Stop My server` to stop your notebook server. Then click `Start My server -> Launch server`, you can start a new notebook server on another host.
### 4. How to install python packages?
python in container can use the packages in users' home. so use `pip2/3 install <package_name> --user` to install packages. Besides, you can rebuild the container and add the packages in.