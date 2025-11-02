import jpype
import json

# Path to your jar and class file (relative or absolute)
jar_path = "org.omg.sysml.interactive-0.52.0-SNAPSHOT-all.jar"
class_path = "."

# Start the JVM
jpype.startJVM(classpath=[jar_path, class_path])

# Import your Java bridge class
SysMLParserService = jpype.JClass('SysMLParserService')

# Example SysML code string
sysml_code = """
package 'Parts Example-1' {
	part def Vehicle {
		part eng : Engine;
	}
	part def Engine {
		part cyl : Cylinder[4..6];
	}
	part def Cylinder;
	part smallVehicle : Vehicle {
		part redefines eng {
			part redefines cyl[4];
		}
	}
	part bigVehicle : Vehicle {
		part redefines eng {
			part redefines cyl[6];
		}
	}
}
"""
ast = SysMLParserService.parseString(sysml_code)
# JPype auto-converts many Java collections
print(json.dumps(ast, indent=2, default=str))