<details>
<summary>📑 Spis treści</summary>

- [1. XML Generator](#1-xml-generator)
- [2. HAL Generator](#2-hal-generator)
- [3. INI Generator](#3-ini-generator)
- [4. DosStyle → UTF-8 LF Converter](#4-dosstyle--utf-8-lf-converter)

</details>

---

<details>
<summary id="1-xml-generator">1. XML Generator</summary>

1.1 Load the .xml ESI file from the manufacturer.
![1.1](images/1.1.png)

1.2 Replace the names of the HAL pins (PDO). 
It replaces the name modes of operation → opmode and a few others; all pin names can be found in the servodriver manual. 
![1.2](images/1.2.png)

1.3 Reduce PDOs to CSP essential.
Keeps the first output group and the first input PDO, keeps essential PDOs for CSP mode; if you want to use CSV mode, target velocity is kept instead of target position. The text can be edited manually. 
![1.3](images/1.3.png)

1.4 Duplicate the slave.
Each click duplicates the text </slave... </slave> and increments the slave index in numerical order. 
![1.4](images/1.4.png)

1.5 Save Xml                           
![1.5](images/1.5.png)

</details>

---

<details>
<summary id="2-hal-generator">2. HAL Generator</summary>

### 2.1
![2.1](images/2.1.png)

### 2.2
![2.2](images/2.2.png)

### 2.3
![2.3](images/2.3.png)

### 2.4
![2.4](images/2.4.png)

</details>

---

<details>
<summary id="3-ini-generator">3. INI Generator</summary>

### 3.1
![3.1](images/3.1.png)

### 3.2
![3.2](images/3.2.png)

### 3.3
![3.3](images/3.3.png)

</details>

---

<details>
<summary id="4-dosstyle--utf-8-lf-converter">4. DosStyle → UTF-8 LF Converter</summary>

### 4.1
![4.1](images/4.1.png)

</details>
