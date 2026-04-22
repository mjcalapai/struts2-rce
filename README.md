
Based on: https://github.com/piesecurity/apache-struts2-CVE-2017-5638

### Usage:
Pre-requisites: have python, docker, maven and a jdk installed

1. clone this repo
1. run mvn clean package in project root
1. run docker build -t hack \.
1. run docker run -d -p 8080:8080 hack
1. once container comes online - verify by running in browser with URL: http://<IP_ADDR>:8080/orders/



README.txt - Rest Showcase Webapp

Rest Showcase is a simple example of REST app build with the REST plugin.

For more on getting started with Struts, see 

* http://cwiki.apache.org/WW/home.html

-------

# Milestone 2




## Project Overview: 
* Apache Struts2 Web framework CVE-2017-5638. 
* The vulnerability in the web framework is the Jakarta Multipart parser. If the Content-Type value is not valid, as it does not match an expected value, an exception is thrown that is then used to display an error message to a user. In this case, we can set the Content-Type to an OGNL expression.


## Protocol Summary
        Messages are handled as
1. Length-prefixed data
2. HTTPS (TLS) for messages sent between implant and listening post
3. Base64 encoding content
4. XOR obfuscation to hide JSON payload structure mitigating against traffic analysis
5. JSON format message payloads




## Attacker: Send HTTP request
   * Injects OGNL(object graph navigation language) expression
   * Executes Shell command that downloads and executes the implant
   * Attacker boots the listening post and the operator CLI (optionally in the same command as the implant download and execution)
      * The attacker will send commands from the operator CLI to the listening post.
      * The listening post will forward the task to the database (Supabase hosted), then encrypt the traffic with the CLI command and send it to the implant. This process will send results to the ‘tasks’ table, which can be seen currently with http:127.0.0.1:5000/tasks. This process will also create an entry on the history table.
      * The implant will execute the command and send an encrypted result back to the listening post. This can be seen on the results table, or http://127.0.0.1:5000/results. This process will also mark the original task on the tasks table as completed, and will update the ‘task_results’ column of the history table.
      * The implant sends the result from the implant back to the operator CLI after decrypting the result.


## Build Instructions:
ENVIRONMENT
   * Clone this repo https://github.com/lltee/struts2-rce (insert our repo name)
   * Run mvn clean package in the project root
   * Run docker built -t hack .
   * Run docker run -d -p 8080:8080 hack
   * Once container is online, it can be verified in browser
      * http://localhost:8080/orders.xhtml
   * Install dependencies in root of repository (struts2-rce):
      * pip install -r requirements.txt
   * Add execution permissions to the loader script
      * chmod +x ./loader.sh
   * Run script in root of repository - example usage:
      * ./loader.sh -b ./Implant/NetSession -p ./persistence.sh -i <TARGET_IP> -l ./listening-post/listening_post.py -c ./controller/controller.py
## Commands


| Command | Description |
|---|---|
| `list-tasks` | View all tasks in the database |
| `list-results` | View results returned by implants |
| `list-history` | View combined task + result history |
| `bundles` | Display available task bundles |
| `addtask <bundle>` | Queue all tasks in a bundle |
| `help` | Show help message |
| `exit` / `quit` | Exit the CLI |


## Task Bundles


| Bundle | Purpose |
|---|---|
| `recon` | Basic system fingerprinting – user, hostname, network, processes, OS |
| `fs` | Filesystem enumeration – SUID binaries, writable directories, text files |
| `persist` | Inspect persistence mechanisms – crontabs, systemd services, `rc.local` |
| `cred` | Credential discovery – env, bash history, SSH keys, sudo, shadow |
| `net` | Network context – ARP, routes, DNS, hosts file, iptables rules |
| `clean` | Anti-forensics – wipe shell history, logs, and `/tmp` |
| `ping` | Lightweight connectivity check to verify implant is alive |


## Usage


```bash
addtask recon
addtask fs
list-tasks
list-results




## Architecture / Threat-Model Diagram
  

Further Details:
* Exploit Payload: HTTP Request injected with ONGL code.
* Implant uses OpenSSL’s default cipher list.
* Certificate is embedded and XOR-encrypted and decrypted at runtime.
* The implant uses HTTPS rather than HTTP or TCP to ensure no data is transmitted as plaintext.














Sources:
https://www.blackduck.com/blog/cve-2017-5638-apache-struts-vulnerability-explained.html
https://github.com/Iletee/struts2-rce
https://shogunlab.gitbook.io/building-c2-implants-in-cpp-a-primer
