
 <div align="left">
 To use the following configurations with servo drives other than Lichuan,               
only the  ```ethercat-conf xml```  file needs to be reviewed and adjusted according to the manual or ESI file provided by the servo drive manufacturer.    
Compare the corresponding index numbers.    
    
Vendor ID. vid="00000766"pid="00000402"  
 also slave idx="0" type="EK1100"
         
Object Group Numbers e.g.   
pdo idx="1600"    
Object numbers e.g.    
pdoEntry idx="6040" bitLen="16"
       
    
Rewiew and Modify these values accordingly for all objects.    
These changes are supposed to be cosmetic only.

or might connect servodives to linux and compere index numbers       
1. Check detected EtherCAT slaves, check slave index eg. slave idx="0" type="EK1100"     
```sudo ethercat slaves```        
     
 2. Display PDOs for all slaves     
```sudo ethercat pdos```       
     
3. Display PDOs for a specific slave, e.g. position 1    
```sudo ethercat pdos -p 1```   
       
4. Display SDO objects for a specific slave       
```sudo ethercat sdos -p 1```     
   
5. Display EtherCAT master information       
```sudo ethercat master```  
  
The ```halPin``` attribute (e.g., halPin="control-word") ```is exclusively used to link ethercat-conf.xml with the HAL file```.
   
Therefore, its value should not be modified becouse must ```match``` the corresponding current signal name in the HAL configuration.          
       
    
 </div>      
