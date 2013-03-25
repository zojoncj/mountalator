#! /usr/bin/env python
import os, sys, subprocess, xml.dom.minidom,time,ConfigParser
from datetime import datetime

config_file=os.path.dirname(os.path.realpath(__file__))+'/config'

if(not os.path.isfile(config_file)):
 print "Config file does not exit!"
 exit()

config = ConfigParser.ConfigParser()
config.read(config_file)
password = config.get('san-info','password')
san_gateway = config.get('san-info','san_gateway')
server_iqn = config.get('san-info','server_iqn')
server_name=config.get('san-info','server_name')
volumes=[]

for volume in config.options('volumes'):
    v=[]
    v.append(volume)
    v.append(config.get('volumes', volume))
    volumes.append(v)

mnt_opts=config.get('mount','mnt_opts')
mnt_point = config.get('mount','mnt_point')

##get snap shots for volume
def get_volume_ss(volume_name):
    get_vol_info = "/usr/bin/sshpass -p %s /usr/bin/ssh -p 16022 -lAdmin %s 'getVolumeInfo volumeName=%s output=xml'" %(password,san_gateway,volume_name)
    out=subprocess.Popen(get_vol_info,stdout=subprocess.PIPE,shell=True).communicate()
    doc=xml.dom.minidom.parseString(out[0])
    current=prev=datetime(1900,1,1,1,1)
    new_mount=''
    complete={}
    ##have to do this 'cause a snapshot will be listed that isn't done snapping
    for node in doc.getElementsByTagName('remoteSnapshot'):
        complete[node.getAttribute('name')]=int(node.getAttribute('percentComplete'))
    for node in doc.getElementsByTagName('snapshot'):
        if(node.getAttribute("deleting") == 'true'):
            break
        c=node.getAttribute("created")
        dt=datetime.strptime(c, "%Y-%m-%dT%H:%M:%SZ")
        exit
        if(current < dt and complete[node.getAttribute('name')] == 100 ):
            current=dt
            new_mount=(node.getAttribute("name"),node.getAttribute("iscsiIqn"))
    return (new_mount)

def make_active(mount_point):
    retval=False
    if(subprocess.call("pvscan 2>/dev/null 1>/dev/null",shell=True)==0):
        if(subprocess.call("vgscan|grep %s|grep ACTIVE 2>/dev/null 1>/dev/null" %(mount_point),shell=True)!=0):
            if(subprocess.call("vgchange -a y %s 2>/dev/null 1>/dev/null" %(mount_point),shell=True)==0):
                retval=True
    else:
        retval=True
    return retval

def unmount(mount_point):
    if(subprocess.call("umount %s/%s 2>/dev/null 1>/dev/null" %(mnt_point,mount_point),shell=True)==0):
        return True
    return False
def mount(mount_point):
    full_path='%s/%s' %(mnt_point,mount_point)
    if not os.path.exists(full_path):
        os.makedirs(full_path)
    if(subprocess.call("mount -o %(ops)s /dev/mapper/%(mp)s-%(mp)s %(fp)s 2>/dev/null 1>/dev/null" %{'ops':mnt_opts,'mp':mount_point,'fp':full_path},shell=True)==0):
        return True
    return False

def discover_targets():
    if(subprocess.call('iscsiadm -m discovery -t sendtargets -p %s 2>/dev/null 1>/dev/null" %san_gateway,shell=True)==0):
        return True
    return False

def iqn_log(iqn,action):
    mode='u' if action=='logout' else 'l'
    if(subprocess.call("iscsiadm -m node -T %s -%s 2>/dev/null 1>/dev/null" %(iqn,mode),shell=True)==0):
        return True
    return False

def assign(ss_name):
    if(subprocess.call("/usr/bin/sshpass -p %s /usr/bin/ssh -p 16022 -l Admin %s \
        'assignVolume volumeName=%s initiator=%s exclusiveAccess=0' 2>/dev/null 1>/dev/null"
        %(password,san_gateway,ss_name,server_iqn),shell=True)==0):
        return True
    return False

def save_running(mp):
    if(subprocess.call("ps aux|grep /exports/%s|grep -v grep 2>/dev/null 1>/dev/null" %mp,shell=True)==1):
      return True
    return False
for volume in volumes:
    mp = volume[1]
    if(save_running(mp)):
        print "Running on %s" %mp
        unmount(mp)
        subprocess.call("vgchange -a n %s 2>/dev/null 1>/dev/null" %mp,shell=True)
        v = volume[0].split('-')[0]
        subprocess.call("i=`iscsiadm -m session |grep :%s|awk '{print $4}'`;iscsiadm -m node -T $i -u 2>/dev/null 1>/dev/null" %v,shell=True)
        mounts=get_volume_ss(volume[0])
        new = mounts[0]
        iqn = mounts[1]
        assign(new)
        discover_targets()
        iqn_log(iqn,'login')
        make_active(mp)
        mount(mp)
print "GTG"
exit()
