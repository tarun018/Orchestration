# Orchestration
1. Uses MongoDB to save the data for running VMS.

2. Performs ssh based on public/private key generated at the start of the script. We only have to enter password twice, i.e. once for saving the public key to the machine using ssh-copy-id and again during scp of image file to machine. 

2. Gets physical machines from src/pm_file.

3. Gets Images from src/image_file.

4. Gets instance types from src/flavor_file.

5. Uses Libvirt to create VM's by first connecting to "qemu:user@ip/system", then defining XML of domain, creating domain.

6. Destroys VM using libvirt's, domain.destroy() and then undefines the xml by domain.undefine()