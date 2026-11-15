
1. To use the following configurations with servo drives other than Lichuan,               
only the  ```ethercat-conf.xml```  file needs to be reviewed and adjusted according to the manual or ESI file provided by the servo drive manufacturer.    
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
     
<br>     
<br>    
<br>    
<br>      
<br>     
```Hal file expplanation```



```loadrt [KINS]KINEMATICS```                                                        # Loading the machine kinematics module

```loadrt [EMCMOT]EMCMOT servo_period_nsec=[EMCMOT]SERVO_PERIOD num_joints=[KINS]JOINTS```  # Loading the motion control module and setting the servo period and number of joints

```loadusr -W lcec_conf ethercat-conf.xml```          # Starting EtherCAT configuration from the XML file

```loadrt cia402 count=1```          # Loading one CIA402 drive module

```loadrt lcec```          # Loading the EtherCAT communication module

```loadrt pid names=x-pid```          # Loading one PID controller for the X axis

```addf lcec.read-all servo-thread```          # Adding EtherCAT data reading to the servo thread

```addf cia402.0.read-all servo-thread```          # Adding X-axis drive data reading to the servo thread

```addf motion-command-handler servo-thread```          # Adding motion command handling to the servo thread

```addf motion-controller servo-thread```          # Adding motion control calculations to the servo thread

```addf x-pid.do-pid-calcs servo-thread```          # Adding X-axis PID calculations to the servo thread

```addf cia402.0.write-all servo-thread```          # Adding X-axis drive command transmission to the servo thread

```addf lcec.write-all servo-thread```          # Adding EtherCAT data transmission to the servo thread

```setp iocontrol.0.emc-enable-in 1```          # Setting the LinuxCNC enable signal
<br>     
<br>        
<br>    
AXIS X / joint.0 / cia402.0 / slave.1```     
<br>
```setp cia402.0.pos-scale 1677721.6```          # Setting the X-axis position scaling factor

```setp cia402.0.velo-scale 1677721.6```          # Setting the X-axis velocity scaling factor

```setp cia402.0.csp-mode 0```          # Setting the CSV mode parameter

```setp x-pid.Pgain 10```          # Setting the proportional PID gain

```setp x-pid.FF1 1```          # Setting the velocity feed-forward coefficient

```setp x-pid.Igain 0```          # Disabling the integral PID gain

```setp x-pid.Dgain 0```          # Disabling the derivative PID gain

```setp x-pid.maxoutput 4000```          # Setting the maximum PID output limit
<br>       
<br>       
<br>       
<br>    


`net X-pos-cmd joint.0.motor-pos-cmd => x-pid.command` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the commanded position to the PID input

`net X-pos-fb cia402.0.pos-fb => joint.0.motor-pos-fb x-pid.feedback` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting actual position feedback to LinuxCNC and PID

`net X-vel-out x-pid.output => cia402.0.velocity-cmd` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the PID output to the drive velocity command

`net X-enable joint.0.amp-enable-out => cia402.0.enable x-pid.enable` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the drive enable signal to CIA402 and PID

`net X-amp-fault cia402.0.drv-fault => joint.0.amp-fault-in` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the drive fault signal to LinuxCNC

`net X-custom-home joint.0.request-custom-homing => cia402.0.home` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the custom homing request

`net X-is-custom-homing cia402.0.stat-homing => joint.0.is-custom-homing` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the homing status signal

`net X-custom-home-done cia402.0.stat-homed => joint.0.custom-homing-finished` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the homing completion signal
<br>     
<br>    
<br>       
`net X-control-word cia402.0.controlword => lcec.0.1.control-word` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the CIA402 control word to EtherCAT

`net X-opmode cia402.0.opmode => lcec.0.1.opmode` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the drive operation mode to EtherCAT

`net X-target-velocity cia402.0.drv-target-velocity => lcec.0.1.target-velocity` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the target velocity to EtherCAT

`net X-actual-position lcec.0.1.actual-position => cia402.0.drv-actual-position` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting actual position feedback from EtherCAT to CIA402

`net X-actual-velocity lcec.0.1.actual-velocity => cia402.0.drv-actual-velocity` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting actual velocity feedback from EtherCAT to CIA402

`net X-opmode-display cia402.0.opmode-display => lcec.0.1.opmode-display` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the displayed operation mode to EtherCAT

`net X-status-word lcec.0.1.status-word => cia402.0.statusword` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the EtherCAT status word to CIA402
<br>
<br>
<br>
**Different NET connections for CSP mode**

The following NET connections are used in CSP mode:

`net X-pos-cmd joint.0.motor-pos-cmd => cia402.0.pos-cmd` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the commanded position to the CIA402 position command

`net X-target-position cia402.0.drv-target-position => lcec.0.1.target-position` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the target position to the EtherCAT drive

`net X-actual-velocity cia402.0.drv-actual-velocity => lcec.0.1.actual-velocity` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the actual velocity signal to EtherCAT

**They replace the following NET connections used in the previous configuration:**

`net X-pos-cmd joint.0.motor-pos-cmd => x-pid.command` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the commanded position to the PID input

`net X-vel-out x-pid.output => cia402.0.velocity-cmd` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the PID output to the CIA402 velocity command

`net X-target-velocity cia402.0.drv-target-velocity => lcec.0.1.target-velocity` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the target velocity to the EtherCAT drive

`net X-actual-position lcec.0.1.actual-position => cia402.0.drv-actual-position` &nbsp;&nbsp;&nbsp;&nbsp; # Connecting the actual position feedback from EtherCAT to CIA402
<br>
<br>
<br>
<br>
<br>

## INI File Explanation




## [EMC]

**Machine configuration**

`MACHINE = Generated_EtherCAT`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the machine name

`DEBUG = 0`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Disabling debug messages

`VERSION = 1.1`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the configuration version

## [DISPLAY]

**Graphical interface configuration**

`DISPLAY = axis`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Selecting the AXIS graphical interface

`EDITOR = gedit`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting Gedit as the default text editor

`POSITION_OFFSET = RELATIVE`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting relative position display

`POSITION_FEEDBACK = ACTUAL`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Displaying actual machine position feedback

`ARCDIVISION = 64`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the arc division resolution

`GRIDS = 10mm 20mm 50mm 100mm 1in 2in 5in 10in`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Defining the available grid spacing values

`MAX_FEED_OVERRIDE = 1.2`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the maximum feed override to 120%

`DEFAULT_LINEAR_VELOCITY = 5`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the default linear velocity to 5 units per second

`MAX_ANGULAR_VELOCITY = 50`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the maximum angular velocity

`MIN_LINEAR_VELOCITY = 0`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the minimum linear velocity

`MAX_LINEAR_VELOCITY = 50`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the maximum linear velocity

`CYCLE_TIME = 0.100`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the display update cycle time to 0.1 seconds

`INTRO_GRAPHIC = linuxcnc.gif`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the startup graphic

`INTRO_TIME = 1`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the startup graphic display time to 1 second

`INCREMENTS = 5mm 1mm .5mm .1mm .05mm .01mm .005mm`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Defining the available manual movement increments

## [KINS]

**Kinematics configuration**

`JOINTS = 3`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the number of machine joints to three

`KINEMATICS = trivkins coordinates=XYZ`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Selecting trivial kinematics with X, Y and Z coordinates

## [TASK]

**Task controller configuration**

`TASK = milltask`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Selecting the milltask task controller

`CYCLE_TIME = 0.010`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the task controller cycle time to 0.01 seconds

## [EMCMOT]

**Motion controller configuration**

`EMCMOT = motmod`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Selecting the LinuxCNC motion controller module

`COMM_TIMEOUT = 1.0`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the communication timeout to 1 second

`SERVO_PERIOD = 1000000`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the servo thread period to 1,000,000 nanoseconds

`HOMEMOD = cia402_homecomp`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Selecting the CIA402 homing component

## [TRAJ]

**Trajectory planner configuration**

`COORDINATES = X Y Z`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Defining the machine coordinate axes

`LINEAR_UNITS = mm`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting linear measurement units to millimeters

`ANGULAR_UNITS = degree`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting angular measurement units to degrees

`DEFAULT_LINEAR_VELOCITY = 5`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the default trajectory velocity

`MAX_LINEAR_VELOCITY = 50`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the maximum trajectory velocity

## [HAL]

**HAL configuration**

`HALFILE = hal.hal`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Loading the main HAL configuration file

`HALUI = halui`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Loading the HAL user interface component

## [EMCIO]

**I/O controller configuration**

`EMCIO = io`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Selecting the LinuxCNC I/O controller

`CYCLE_TIME = 0.100`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the I/O controller cycle time to 0.1 seconds

## [RS274NGC]

**G-code interpreter configuration**

`PARAMETER_FILE = gcodeparam.var`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the G-code parameter file

## [AXIS_X]

**X-axis configuration**

`MAX_VELOCITY = 50`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the maximum X-axis velocity

`MAX_ACCELERATION = 100`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the maximum X-axis acceleration

`MIN_LIMIT = -1000`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the minimum X-axis travel limit

`MAX_LIMIT = 1000`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the maximum X-axis travel limit

## [JOINT_0]

**Joint 0 configuration**

`TYPE = LINEAR`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Defining joint 0 as a linear joint

`HOME = 0`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the joint home position to zero

`MIN_LIMIT = -1000`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the minimum joint travel limit

`MAX_LIMIT = 1000`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the maximum joint travel limit

`MAX_VELOCITY = 50`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the maximum joint velocity

`MAX_ACCELERATION = 100`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the maximum joint acceleration

`FERROR = 1000`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the maximum permitted following error

`MIN_FERROR = 1000`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the minimum following error threshold

`HOME_ABSOLUTE_ENCODER = 2`&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Setting the absolute encoder homing mode



        


    
