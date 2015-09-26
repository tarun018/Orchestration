def getXML(id, name, memory, cpu, source):
	xml = """
	<domain type='qemu' id='%s'>
	<name>%s</name>
	<memory unit='KiB'>%s</memory>
	<currentMemory unit='KiB'>524</currentMemory>
	<vcpu>%s</vcpu>
	<os>
		<type arch='i686' machine='pc-1.1'>hvm</type>
		<boot dev='cdrom'/>
		<boot dev='hd'/>
	</os>
	<features>
		<acpi/>
		<apic/>
		<pae/>
	</features>
	<clock offset='utc'/>
	<on_poweroff>destroy</on_poweroff>
	<on_reboot>restart</on_reboot>
	<on_crash>restart</on_crash>
	<devices>
		<disk type='file' device='cdrom'>
			<driver name='qemu' type='raw'/>
			<target dev='hda' bus='ide'/>
		</disk>
		<disk type='file' device='cdrom'>
			<driver name='qemu' type='raw'/>
			<source file='%s'/>
			<target dev='hdc' bus='ide'/>
			<readonly/>
		</disk>
	</devices>
</domain>"""% (id, name, memory, cpu, source)
	return xml