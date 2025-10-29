### You need at least java 18

- **Java 21** (JDK from Eclipse Adoptium or equivalent)
  - Download from: https://adoptium.net/
  - This project was developed with Eclipse Adoptium JDK 21.0.6.7

### Clone the repo you will have:

1. **Standalone JAR** 
   - `org.omg.sysml.interactive-0.52.0-SNAPSHOT-all.jar`
   - See "Building the Standalone JAR" section below

2. **SysML Standard Library**
   - Located in the `sysml.library` directory of the SysML v2 Pilot Implementation
   - Required for resolving standard imports (ISQ, SI, ScalarValues, etc.)

## Repository Structure

```
workspace/
├── ParseSysML.java              # Main parser entry point
├── SysMLSerializer.java         # Custom AST-to-code serializer
├── test2.sysml                  # Example test file
├── org.omg.sysml.interactive-0.52.0-SNAPSHOT-all.jar  # Standalone JAR
└── sysml.library/               # Standard library directory (from SysML v2 repo)
```

## Setup Instructions

### 1. Install Java 21

**Windows (inside CMD):**
# Set environment variables:
set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.6.7-hotspot

set PATH=%JAVA_HOME%\bin;%PATH%



**Important:** The `sysml.library` directory must be present to resolve standard library imports like `ISQ::*`, `SI::*`, and `ScalarValues::*`.

### 3. Update Library Path in ParseSysML.java

Edit `ParseSysML.java` and update line 32 to point to your `sysml.library` directory:

```java
String libraryPath = "C:/path/to/your/workspace/sysml.library";
```

Also update the path to the test file in line 41 inside `ParseSysML.java`:
```java
String libraryPath = "C:/Haitham/sysml-test/test2.sysml";
```

## Usage

### Compile

**Windows:**
```batch
javac -cp org.omg.sysml.interactive-0.52.0-SNAPSHOT-all.jar ParseSysML.java SysMLSerializer.java
```

### Run

**Windows:**
```batch
java -cp .;org.omg.sysml.interactive-0.52.0-SNAPSHOT-all.jar ParseSysML
```

### What It Does

The program will:
1. Initialize the SysML v2 parser with proper standalone setup
2. Load the standard library from the specified path
3. Parse the input file (`test2.sysml`) into an AST
4. Print the AST structure to console
5. Serialize the AST back to SysML code using the custom serializer
6. Print the serialized code
