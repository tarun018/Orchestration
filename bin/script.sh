#!/bin/bash
sudo apt-get install mongodb
sudo apt-get install python-pymongo
cd ../src/
ssh-keygen -t RSA
filename="pm_file"
i=0
while read line
do
    array[ $i ]="$line"        
    (( i++ ))
done < "$filename"
for i in "${array[@]}"
do
   ssh-copy-id "$i"
   ssh-add
done
python app.py pm_file image_file flavor_file
ssh-add -D
