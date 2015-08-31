from uuid import uuid4
import json

images = []
def getImages(Imagefile):
	imageID = 1
	file = open(Imagefile, "r")
	for line in file.readlines():
		line = line.rstrip()
		imageLocation = line
		imageName = line.split('/')[-1]
		images.append((imageID, imageLocation, imageName))
		imageID += 1
	return images


machines = []
def getMachines(MachineFile):
	machineID = 1
	file = open(MachineFile, "r")
	for line in file:
		line = line.rstrip()
		split1 = line.split('@')
		user = split1[0]
		ip = split1[1]
		machines.append((machineID, str(uuid4()), user, ip))
		machineID += 1
	return machines

instance_types = []
def getVmTypes(VMFile):
	file = open(VMFile, "r")
	val = json.loads(file.read())[u'types']
	instance_types = val
	return val