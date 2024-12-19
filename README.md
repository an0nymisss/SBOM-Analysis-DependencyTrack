## SBOM_Analysis_DependencyTrack
Python script to fetch component info from DependencyTrack API and retrieve their version release dates (for both installed and latest versions).

### Usage: sudo python date_automation.py

(sudo permission is required to run docker containers from via script. Alternatively, you can add your user in the 'docker' group.)

#### Prerequisites: 

\- Enter the base url of your DependencyTrack instance in the BASE\_URL global variable.<br>
\- Update the 'PROJECT\_UUID' global variable with the respective project uuid you want to analyze (Refer your DependencyTrack instance for this).<br>
\- Create an 'api_key' file to store the API key from DependencyTrack. Now you can run the python script.

#### Notes:

\- This script will pull the necessary docker images, you can clean them up later if you wish. The corresponding container processes are already cleaned up automatically.<br>
\- Currently, NPM, Maven, Go Modules, Cargo, Composer, Gem, and PyPi are integrated. More repo integrations will follow in the future.
