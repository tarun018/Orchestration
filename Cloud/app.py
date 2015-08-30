from flask import Flask, jsonify, make_response, request
import parse, xml
import os
import sys
import libvirt
app = Flask(__name__)

VM_id = 38200

@app.route("/")
def hello():
	return "Hello All. Welcome to the world of Virtualization!"

@app.route("/server/pm/list/")
def listMachines():
	printMachines = []
	for every in list(db.machinesdb.find()):
		printMachines.append(every['pm'][0])
	return jsonify({"pmids" : printMachines})

@app.route("/server/image/list/")
def listImages():
	printImages = []
	for every in list(db.imagesdb.find()):
		toprint = {}
		toprint['id'] = every['image'][0]
		toprint['name'] = every['image'][-1]
		printImages.append(toprint)
	return jsonify({"images" : printImages})

@app.route("/server/vm/types")
def listvmtypes():
	return jsonify({"VMTypes" : vmtypes})

@app.route("/server/vm/create", methods=['GET'])
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
		image_user = imageDetails[1]
		image_ip = imageDetails[2]
		image_location = imageDetails[3]
		image_name = imageDetails[4]
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

	imageTransfer(selected_physical_machine, imageDetails)
	lht = int(db.vms.count())
	VM_id = 38201 + lht
	VMIDList.append(VM_id)
	VM_name = name
	VM_ram = int(instance_ram * 1000)
	VM_cpu = instance_cpu
	VM_Image_source = image_location

	VM_xml = xml.getXML(int(VM_id), VM_name, int(VM_ram), int(VM_cpu), VM_Image_source)
	VMs[str(VM_id)] = {}
	VMs[str(VM_id)]['id'] = VM_id
	VMs[str(VM_id)]['name'] = VM_name
	VMs[str(VM_id)]['ram'] = VM_ram
	VMs[str(VM_id)]['cpu'] = VM_cpu
	VMs[str(VM_id)]['xml'] = VM_xml	
	VMs[str(VM_id)]['image'] = imageDetails
	VMs[str(VM_id)]['pm'] = selected_physical_machine
	VMs[str(VM_id)]['instance'] = instanceDetails
	print "Trying to connect"
	try:
		connection = libvirt.open("qemu:///system")
		connection.defineXML(VM_xml)
		print "Connection:"
		dom = connection.lookupByName(VM_name)
		print "Domain:"
		print dom.create()
		addVM(VM_id)
		result = "{\n%s\n}" % str(VM_id)
		connection.close()
		#return result
		return jsonify({"vmid" : VM_id})
	except:
		print "Failed"
		VMs.pop(str(VM_id))
		VMIDList.remove(VM_id)
		return jsonify(status=0)

@app.route("/server/vm/query", methods=['GET'])
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

@app.route("/server/vm/destroy", methods=['GET'])
def VM_Destroy():
	arguments = request.args
	requestedID = int(arguments['vmid'])
	if isVMValid(requestedID) == False:
		return jsonify(status=0)
	for x in list(db.vms.find()):
		if int(x['vms']['id']) == int(requestedID):
			conn = libvirt.open("qemu:///system")
			dom = conn.lookupByName(str(x['vms']['name']))
			try:
				dom.destroy()
				dom.undefine()
				db.vms.remove({'idto' : requestedID})
				conn.close()
				return jsonify(status=1)
			except:
				conn.close()
				return jsonify(status=0)
	return jsonify(status=0)

@app.route("/server/pm/listvms", methods=['GET'])
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
		return len(toprint)
	return jsonify({"vmids" : toprint})

@app.route("/server/pm/query", methods=['GET'])
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
			toprint['vms'] = listvms(-8)
			return jsonify({"PMQuery" : toprint})
	return jsonify(status=0)

			
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
	image_user = imageDetails[1]
	image_ip = imageDetails[2]
	image_location = imageDetails[3]
	image_name = imageDetails[4]

	if image_user == selected_machine_user and image_ip == selected_machine_ip:
		return 1
	print "Sending file"
	t = os.system("sudo scp -3 " + image_user + "@" + image_ip + ":" + image_location + " " + selected_machine_user + "@" + selected_machine_ip + ":/home/ubuntu/")
	if t!=0:
		print "Something is wrong!"

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

def closeConnection():
	client = pymongo.MongoClient()
	client.close()

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
	VMIDList = []
	addVM()
	app.run(debug=True)