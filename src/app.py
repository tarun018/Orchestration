from flask import Flask, jsonify, make_response, request
import parse, xml, attach
import os
import sys
import libvirt
import rados
import subprocess
import rbd
from random import choice

app = Flask(__name__)

VM_id = 38200
VOL_id = 157
CONF_FILE = "/etc/ceph/ceph.conf"
POOL = 'test'
HOST = 'tg'
BLOCK_XML = ""
VOL_Names = []

@app.route("/")
def hello():
	return "Hello All. Welcome to the world of Virtualization!"

@app.route("/volume/create",methods=['GET'])
def createVolume():
	arguments = request.args
	name = str(arguments['name'])
	size = int(arguments['size'])
	global VOL_Names
	if name in VOL_Names:
		return jsonify(volumeid=0)
	size = (1024**3) * size
	global rbdInstance
	global ioctx
	try:
		rbdInstance.create(ioctx, name, size)
		os.system('sudo rbd map %s --pool %s --name client.admin'%(name,POOL))
	except:
		jsonify(volumeid=0)
	volDetails = {}
	volumeID = VOL_id + int(db.vols.count())
	volDetails[str(volumeID)] = {}
	volDetails[str(volumeID)]['name'] = name
	volDetails[str(volumeID)]['size'] = size
	volDetails[str(volumeID)]['status'] = "available"
	volDetails[str(volumeID)]['VMid'] = None
	volDetails[str(volumeID)]['dev_name'] = getDeviceName()
	db.vols.insert({'idto' : volumeID, 'vol' : volDetails[str(volumeID)]})
	return jsonify(volumeid=volumeID)

@app.route("/volume/query",methods=['GET'])
def queryVolume():
	arguments = request.args
	volumeIDtoquery = int(arguments['volumeid'])
	for x in list(db.vols.find()):
		if int(x['idto']) == volumeIDtoquery:
			volInfo = x['vol']
			presentStatus = volInfo['status']
			if presentStatus == "available":
				return jsonify(volumeid = volumeIDtoquery,
							   name = volInfo['name'],
							   size = (int(volInfo['size'])/(1024**3)),
							   status = volInfo['status'])
			elif presentStatus == "attached":
				return jsonify(volumeid = volumeIDtoquery,
							   name = volInfo['name'],
							   size = (int(volInfo['size'])/(1024**3)),
							   status = volInfo['status'],
							   vmid = volInfo['VMid'])
	return jsonify(error = "volumeid : %s does not exist"%(volumeIDtoquery))	

@app.route("/volume/destroy",methods=['GET'])
def destroyVolume():
	arguments = request.args
	volumeIDtoDelete = int(arguments['vmid'])
	for x in list(db.vols.find()):
		if int(x['idto']) == volumeIDtoDelete and str(x['vol']['status']) == "available":
			try:
				imageName = str(x['vol']['name'])
				os.system('sudo rbd unmap /dev/rbd/%s/%s'%(POOL,imageName))
				rbdInstance.remove(ioctx,imageName)
				db.vols.remove({'idto' : volumeIDtoDelete})
				return jsonify(status=1)
			except:
				return jsonify(status=0)
	return jsonify(status=0)

@app.route("/volume/attach", methods=['GET'])
def attachVolume():
	arguments = request.args
	vmid = int(arguments['vmid'])
	volid = int(arguments['volumeid'])
	if isVolValid(volid) == False:
		return jsonify(status=0)
	if isVMValid(vmid) == False:
		return jsonify(status=0)
	vminfo = {}
	volinfo = {}
	for x in list(db.vms.find()):
		if int(x['idto']) == vmid:
			vminfo = x['vms']
	for x in list(db.vols.find()):
		if int(x['idto']) == volid:
			volinfo = x['vol']
	selected_machine_user = vminfo['pm'][2]
	selected_machine_ip = vminfo['pm'][3]
	VM_name = vminfo['name']
	Image_name = volinfo['name']
	dev = volinfo['dev_name']

	connection = libvirt.open("qemu+ssh://" + selected_machine_user + "@" + selected_machine_ip + "/system")
	dom = connection.lookupByName(VM_name)
	confXML = attach.getXML(str(Image_name), str(HOST), str(POOL), str(dev))
	try:
		dom.attachDevice(confXML)
		volinfo['VMid'] = vmid
		volinfo['status'] = "attached"
		db.vols.remove({'idto' : volid})
		db.vols.insert({'idto' : volid , 'vol' : volinfo})
		connection.close()
		return jsonify(status=1)
	except:
		connection.close()
		return jsonify(status=0)

@app.route("/volume/detach", methods=['GET'])
def detachVolume():
	arguments = request.args
	volid = int(arguments['volumeid'])
	if isVolValid(volid) == False:
		return jsonify(status=0)
	volinfo = {}
	for x in list(db.vols.find()):
		if int(x['idto']) == volid:
			volinfo = x['vol']
	if volinfo['status'] != "attached":
		return jsonify(status=0)
	vmid = volinfo['VMid']
	vminfo = {}
	for x in list(db.vms.find()):
		if int(x['idto']) == vmid:
			vminfo = x['vms']
	selected_machine_user = vminfo['pm'][2]
	selected_machine_ip = vminfo['pm'][3]
	VM_name = vminfo['name']
	Image_name = volinfo['name']
	dev = volinfo['dev_name']

	connection = libvirt.open("qemu+ssh://" + selected_machine_user + "@" + selected_machine_ip + "/system")
	dom = connection.lookupByName(VM_name)
	confXML = attach.getXML(str(Image_name), str(HOST), str(POOL), str(dev))
	try:
		dom.detachDevice(confXML)
		connection.close()
		volinfo['VMid'] = None
		volinfo['status'] = "available"
		db.vols.remove({'idto' : volid})
		db.vols.insert({'idto' : volid , 'vol' : volinfo})
		return jsonify(status=1)
	except:
		connection.close()
		return jsonify(status=0)

@app.route("/pm/list/")
def listMachines():
	printMachines = []
	for every in list(db.machinesdb.find()):
		printMachines.append(every['pm'][0])
	return jsonify({"pmids" : printMachines})

@app.route("/image/list/")
def listImages():
	printImages = []
	for every in list(db.imagesdb.find()):
		toprint = {}
		toprint['id'] = every['image'][0]
		toprint['name'] = every['image'][-1]
		printImages.append(toprint)
	return jsonify({"images" : printImages})

@app.route("/vm/types")
def listvmtypes():
	return jsonify({"VMTypes" : vmtypes})

@app.route("/vm/create", methods=['GET'])
def createVM():
	arguments = request.args
	name = str(arguments['name'])
	imageID = int(arguments['image_id'])
	instanceID = int(arguments['instance_type'])

	instanceDetails = getVMInstanceTypeDetails(instanceID)
	if instanceDetails != 0:
		instance_tid = instanceDetails['tid']
		instance_cpu = instanceDetails['cpu']
		instance_ram = instanceDetails['ram']
		instance_disks = instanceDetails['disk']
	else:
		print "No such VM Type"
		return jsonify(status=0)
	print "Instance Details Extracted"

	imageDetails = getImageDetails(imageID)
	if imageDetails != 0:
		image_iid = imageDetails[0]
		image_location = imageDetails[1]
		image_name = imageDetails[2]
	else:
		print "No such Image ID"
		return jsonify(status=0)
	print "Image Details Extracted"

	selected_physical_machine = Scheduler_FIFO(instanceDetails)
	if selected_physical_machine != 0:
		selected_machine_ID = selected_physical_machine[0]
		selected_machine_UUID = selected_physical_machine[1]
		selected_machine_user = selected_physical_machine[2]
		selected_machine_ip = selected_physical_machine[3]
	else:
		print "No machine matches the requested criteria"
		return jsonify(status=0)
	print "Machine Details Extracted"

	loc = imageTransfer(selected_physical_machine, imageDetails)
	lht = int(db.vms.count())
	VM_id = 38201 + lht
	VM_name = name
	VM_ram = int(instance_ram * 1000)
	VM_cpu = instance_cpu
	VM_Image_source = loc + image_name

	VM_xml = xml.getXML(int(VM_id), VM_name, int(VM_ram), int(VM_cpu), VM_Image_source)
	VMs[str(VM_id)] = {}
	VMs[str(VM_id)]['id'] = VM_id
	VMs[str(VM_id)]['name'] = VM_name
	VMs[str(VM_id)]['ram'] = VM_ram
	VMs[str(VM_id)]['cpu'] = VM_cpu
	VMs[str(VM_id)]['image'] = imageDetails
	VMs[str(VM_id)]['pm'] = selected_physical_machine
	VMs[str(VM_id)]['instance'] = instanceDetails
	print "Trying to connect"
	try:
		connection = libvirt.open("qemu+ssh://" + selected_machine_user + "@" + selected_machine_ip + "/system")
		connection.defineXML(VM_xml)
		dom = connection.lookupByName(VM_name)
		dom.create()
		addVM(VM_id)
		#result = "{\n%s\n}" % str(VM_id)
		#connection.close()
		#return result
		return jsonify({"vmid" : VM_id})
	except:
		print "Failed"
		VMs.pop(str(VM_id))
		return jsonify(status=0)

@app.route("/vm/query", methods=['GET'])
def VM_Query():
	arguments = request.args
	requestedID = int(arguments['vmid'])
	if isVMValid(requestedID) == False:
		return jsonify(status=0)
	for x in list(db.vms.find()):
		if int(x['vms']['id']) == int(requestedID):
			toprint = {}
			vminfo = x['vms'] 
			toprint['vmid'] = vminfo['id']
			toprint['name'] = vminfo['name']
			toprint['instance_type'] = vminfo['instance']['tid']
			toprint['pmid'] = vminfo['pm'][0]
			return jsonify({"VM_Query" : toprint})
	return jsonify(status=0)

@app.route("/vm/destroy", methods=['GET'])
def VM_Destroy():
	arguments = request.args
	requestedID = int(arguments['vmid'])
	if isVMValid(requestedID) == False:
		return jsonify(status=0)
	for x in list(db.vms.find()):
		if int(x['vms']['id']) == int(requestedID):
			selected_machine_user = x['vms']['pm'][2]
			selected_machine_ip = x['vms']['pm'][3]
			print selected_machine_user, selected_machine_ip
			conn = libvirt.open("qemu+ssh://" + selected_machine_user + "@" + selected_machine_ip + "/system")
			print str(x['vms']['name'])
			dom = conn.lookupByName(str(x['vms']['name']))
			try:
				dom.destroy()
				dom.undefine()
				db.vms.remove({'idto' : requestedID})
				#conn.close()
				return jsonify(status=1)
			except:
				#conn.close()
				return jsonify(status=0)
	return jsonify(status=0)

@app.route("/pm/listvms", methods=['GET'])
def listvms(pmquery=None):
	arguments = request.args
	requestedID = int(arguments['pmid'])
	if isPMValid(requestedID) == False:
		return jsonify(status=0)
	toprint = []
	for x in list(db.vms.find()):
		if int(x['vms']['pm'][0]) == int(requestedID):
			toprint.append(int(x['vms']['id']))
	if pmquery == -8:
		return toprint
	return jsonify({"vmids" : toprint})

@app.route("/pm/query", methods=['GET'])
def pmQuery():
	toprint = {}
	arguments = request.args
	requestedID = int(arguments['pmid'])
	if isPMValid(requestedID) == False:
		return jsonify(status=0)
	for x in list(db.machinesdb.find()):
		if int(x['pm'][0]) == int(requestedID):
			toprint['pmid'] = x['pm'][0]
			machine = x['pm']
			machine_ID = machine[0]
			machine_UUID = machine[1]
			machine_user = machine[2]
			machine_ip = machine[3]
			os.system("ssh " + machine_user + "@" + machine_ip + " nproc >> data")
			os.system("ssh " + machine_user + "@" + machine_ip + " free -m | grep 'Mem:' | awk '{print $2}' >> data")
			os.system("ssh " + machine_user + "@" + machine_ip + " free -m | grep 'Mem:' | awk '{print $4}' >> data")
			f = open("data", "r")
			cpu = f.readline().rstrip()
			mem = f.readline().rstrip()
			toprint['capacity'] = {}
			toprint['capacity']['cpu'] = cpu
			toprint['capacity']['ram'] = mem
			toprint['capacity']['disk'] = 160
			free = f.readline().rstrip()
			toprint['free'] = {}
			toprint['free']['cpu'] = cpu
			toprint['free']['ram'] = free
			toprint['free']['disk'] = 160
			f.close()
			os.system("rm -rf data")
			toprint['vms'] = len(listvms(-8))
			return jsonify({"PMQuery" : toprint})
	return jsonify(status=0)

def isVolValid(Volid):
	for x in list(db.vols.find()):
		if int(x['idto']) == int(Volid):
			return True
	return False

def isVMValid(VMid):
	for x in list(db.vms.find()):
		if int(x['idto']) == int(VMid):
			return True
	return False

def isPMValid(PMid):
	for x in list(db.machinesdb.find()):
		if int(x['pm'][0]) == int(PMid):
			return True
	return False

def getVMInstanceTypeDetails(instance_id):
	for i in vmtypes:
		if i[u'tid'] == instance_id:
			return i
	return 0

def getImageDetails(image_id):
	for i in list(db.imagesdb.find()):
		if i['image'][0] == image_id:
			return i['image']
	return 0

def Scheduler_FIFO(instanceDetails):
	for x in list(db.machinesdb.find()):
		machine = x['pm']
		machine_ID = machine[0]
		machine_UUID = machine[1]
		machine_user = machine[2]
		machine_ip = machine[3]

		print "Ram"
		os.system("ssh " + machine_user + "@" + machine_ip + " free -m | grep 'Mem:' | awk '{print $4}' >> data")
		print "cpus"
		os.system("ssh " + machine_user + "@" + machine_ip + " grep processor /proc/cpuinfo | wc -l >> data")
		f = open("data", "r")
		machine_free_ram = f.readline().rstrip()
		machine_cpus = f.readline().rstrip()
		os.system("rm -rf data")

		if int(machine_free_ram) >= int(instanceDetails['ram']):
			if int(machine_cpus) >= int(instanceDetails['cpu']):
				return machine
	return 0

def imageTransfer(physical_machine, imageDetails):
	selected_machine_ID = physical_machine[0]
	selected_machine_UUID = physical_machine[1]
	selected_machine_user = physical_machine[2]
	selected_machine_ip = physical_machine[3]	

	image_iid = imageDetails[0]
	image_location = imageDetails[1]
	image_name = imageDetails[2]

	os.system("sudo scp " + image_location + " " + selected_machine_user + "@" + selected_machine_ip + ":/home/" + selected_machine_user)
	return "/home/" + selected_machine_user + "/"

def addVM(VmID=None):
	if VmID == None and len(list(db.vms.find())) == 0:
		for x in VMs:
			db.vms.insert({'idto' : VMs[str(x)]['id'], 'vms' : VMs[str(x)]})
	elif VmID != None:
		db.vms.insert({'idto' : VmID, 'vms' : VMs[str(VmID)]})

def get_db():
	from pymongo import MongoClient
	client = MongoClient('localhost:27017')
	db = client.myFirstMB
	return db

def establish_connection():
	cluster = rados.Rados(conffile=CONF_FILE)
	cluster.connect()
	if POOL not in cluster.list_pools():
		cluster.create_pool(POOL)
	global ioctx
	ioctx = cluster.open_ioctx(POOL)
	global rbdInstance
	rbdInstance = rbd.RBD()

def getDeviceName():
	alpha = choice('efghijklmnopqrstuvwxyz')
	numeric = choice([x for x in range(1,10)])
	return 'sd' + str(alpha) + str(numeric)

def getHostName():
	global HOST
	monProc = subprocess.Popen("ceph mon_status", shell=True, bufsize=0, stdout=subprocess.PIPE, universal_newlines=True)
	monDict = eval(monProc.stdout.read())
	HOST = monDict['monmap']['mons'][0]['name']
	#print HOST

if __name__ == '__main__':
	if len(sys.argv) < 4:
		print "Usage: python app.py Machines Images VM_Types"
		exit(1)
	machines = parse.getMachines(sys.argv[1])
	db = get_db()
	db.machinesdb.drop()
	[ db.machinesdb.insert({'pm':machine}) for i,machine in enumerate(machines) ]
	images = parse.getImages(sys.argv[2])
	db.imagesdb.drop()
	[ db.imagesdb.insert({'image':image}) for i,image in enumerate(images) ]
	vmtypes = parse.getVmTypes(sys.argv[3])
	VMs = {}
	addVM()
	establish_connection()
	getHostName()
	app.run(debug=True)