import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.util.EcoreUtil;
import org.omg.sysml.lang.sysml.*;

public class SysMLSerializer {
    private StringBuilder output;
    private int indentLevel;
    
    public SysMLSerializer() {
        this.output = new StringBuilder();
        this.indentLevel = 0;
    }
    
    public String serialize(EObject root) {
        output = new StringBuilder();
        indentLevel = 0;
        visit(root);
        return output.toString();
    }
    
    private void visit(EObject node) {
        if (node instanceof ConjugatedPortDefinition) {
            return;
        } else if (node instanceof org.omg.sysml.lang.sysml.Package) {
            visitPackage((org.omg.sysml.lang.sysml.Package) node);
        } else if (node instanceof InterfaceDefinition) {
            visitInterfaceDefinition((InterfaceDefinition) node);
        } else if (node instanceof PortDefinition) {
            visitPortDefinition((PortDefinition) node);
        } else if (node instanceof PartDefinition) {
            visitPartDefinition((PartDefinition) node);
        } else if (node instanceof PortUsage) {
            visitPortUsage((PortUsage) node);
        } else if (node instanceof PartUsage) {
            visitPartUsage((PartUsage) node);
        } else if (node instanceof AttributeUsage) {
            visitAttributeUsage((AttributeUsage) node);
        } else if (node instanceof ReferenceUsage) {
            visitReferenceUsage((ReferenceUsage) node);
        } else if (node instanceof NamespaceImport) {
            visitNamespaceImport((NamespaceImport) node);
        } else if (node instanceof Documentation) {
            visitDocumentation((Documentation) node);
        } else if (node instanceof Comment) {
            visitComment((Comment) node);
        } else if (node instanceof FlowUsage) {
            visitFlowUsage((FlowUsage) node);
        } else if (node instanceof EndFeatureMembership) {
            visitEndFeatureMembership((EndFeatureMembership) node);
        } else if (node instanceof OwningMembership) {
            visitOwningMembership((OwningMembership) node);
        } else if (node instanceof FeatureMembership) {
            visitFeatureMembership((FeatureMembership) node);
        } else if (node instanceof org.omg.sysml.lang.sysml.Namespace) {
            visitNamespace((org.omg.sysml.lang.sysml.Namespace) node);
        } else {
            // unknown types, get children
            for (EObject child : node.eContents()) {
                visit(child);
            }
        }
    }

    private void visitNamespace(org.omg.sysml.lang.sysml.Namespace ns) {
        // Namespace is just a container, visit its children
        for (EObject child : ((EObject)ns).eContents()) {
            visit(child);
        }
    }
    
    private void visitPackage(org.omg.sysml.lang.sysml.Package pkg) {
        writeIndent();

        System.out.println("DEBUG visitPackage: " + pkg.getDeclaredName());
        System.out.println("       Number of direct children: " + pkg.eContents().size());
        for (EObject child : pkg.eContents()) {
            System.out.println("       Direct child type: " + child.eClass().getName());
        }


        output.append("package ");
        
        // Handle package names with spaces (need quotes)
        String name = pkg.getDeclaredName();
        if (name != null) {
            if (name.contains(" ") || name.contains("-")) {
                output.append("'").append(name).append("'");
            } else {
                output.append(name);
            }
        }
        
        output.append(" {\n");
        indentLevel++;
        
        // Visit children
        for (EObject child : pkg.eContents()) {
            visit(child);
        }
        
        indentLevel--;
        writeIndent();
        output.append("}\n");
    }
    
    private void visitNamespaceImport(NamespaceImport imp) {
        writeIndent();
        
        // Check if it's private
        if (imp.getVisibility() == VisibilityKind.PRIVATE) {
            output.append("private ");
        }
        
        output.append("import ");
        
        // Get the imported namespace
        org.omg.sysml.lang.sysml.Namespace importedNamespace = imp.getImportedNamespace();
        System.err.println("DEBUG Import: importedNamespace = " + importedNamespace);
        if (importedNamespace != null) {
            // Force proxy resolution
            importedNamespace.eClass();
            
            // Try to get qualified name
            String importName = importedNamespace.getQualifiedName();
            System.err.println("       qualifiedName = " + importedNamespace.getQualifiedName());
            System.err.println("       name = " + importedNamespace.getName());
            if (importName == null) {
                importName = importedNamespace.getName();
            }
            
            if (importName != null) {
                output.append(importName);
                // Check if it's a wildcard import (import all)
                output.append("::*");
            }
        }
        
        output.append(";\n");
    }
    
    private void visitDocumentation(Documentation doc) {
        writeIndent();
        output.append("doc\n");
        writeIndent();
        output.append("/*\n");
        
        // Get the documentation body
        String body = doc.getBody();
        if (body != null && !body.trim().isEmpty()) {
            String[] lines = body.split("\n");
            for (String line : lines) {
                if (!line.trim().isEmpty()) {
                    writeIndent();
                    output.append(" * ").append(line.trim()).append("\n");
                }
            }
        }
        
        writeIndent();
        output.append(" */\n\n");
    }
    
    private void visitComment(Comment comment) {
        writeIndent();
        output.append("/* ");
        
        String body = comment.getBody();
        if (body != null) {
            output.append(body.trim());
        }
        
        output.append(" */\n\n");
    }
    
    private void visitPartDefinition(PartDefinition part) {
        writeIndent();
        output.append("part def ");
        
        String name = part.getDeclaredName();
        if (name != null) {
            output.append(name);
        }
        
        // Check if it has children (features)
        if (!part.eContents().isEmpty()) {
            output.append(" {\n");
            indentLevel++;
            
            for (EObject child : part.eContents()) {
                visit(child);
            }
            
            indentLevel--;
            writeIndent();
            output.append("}\n");
        } else {
            output.append(";\n");
        }
    }
    
    private void visitInterfaceDefinition(InterfaceDefinition iface) {
        writeIndent();
        output.append("interface def ");
        
        String name = iface.getDeclaredName();
        if (name != null) {
            output.append(name);
        }
        
        // Check if it has children (features)
        if (!iface.eContents().isEmpty()) {
            output.append(" {\n");
            indentLevel++;
            
            for (EObject child : iface.eContents()) {
                visit(child);
            }
            
            indentLevel--;
            writeIndent();
            output.append("}\n");
        } else {
            output.append(";\n");
        }
    }
    
    private void visitPortDefinition(PortDefinition port) {
        writeIndent();
        output.append("port def ");
        
        String name = port.getDeclaredName();
        if (name != null) {
            output.append(name);
        }
        
        boolean hasMeaningfulChildren = false;
        for (EObject child : port.eContents()) {
            // Skip container nodes and check their contents
            if (child instanceof OwningMembership || child instanceof FeatureMembership) {
                for (EObject grandchild : child.eContents()) {
                    if (!(grandchild instanceof ConjugatedPortDefinition)) {
                        hasMeaningfulChildren = true;
                        break;
                    }
                }
            }
            if (hasMeaningfulChildren) break;
        }

        // Check if it has children (features)
        if (hasMeaningfulChildren) {
            output.append(" {\n");
            indentLevel++;
            
            for (EObject child : port.eContents()) {
                visit(child);
            }
            
            indentLevel--;
            writeIndent();
            output.append("}\n");
        } else {
            output.append(";\n");
        }
    }

    private void visitPortUsage(PortUsage usage) {
        writeIndent();
        
        System.err.println("DEBUG visitPortUsage: name=" + usage.getDeclaredName() + 
                           ", isEnd=" + usage.isEnd());


        if (usage.isEnd()) {
            output.append("end ");
        } else {
            output.append("port ");
        }
        
        String name = usage.getDeclaredName();
        if (name != null) {
            output.append(name);
        }
        
        // Look for typing information (e.g., : AxleMountIF)
        for (EObject child : usage.eContents()) {
            if (child instanceof FeatureTyping) {
                FeatureTyping typing = (FeatureTyping) child;
                Type type = typing.getType();
                if (type != null) {
                    // Force proxy resolution
                    type.eClass();
                    if (type.getDeclaredName() != null) {
                        output.append(": ").append(type.getDeclaredName());
                    }
                }
                break;
            }
        }
        
        output.append(";\n");
    }

    private void visitPartUsage(PartUsage usage) {

        writeIndent();
        output.append("part ");
        
        boolean isRedefine = false;
        for (EObject child : usage.eContents()) {
            if (child instanceof Redefinition) {
                Redefinition redef = (Redefinition) child;
                Feature redefinedFeature = redef.getRedefinedFeature();

                if (redefinedFeature != null) {
                    
                    
                    redefinedFeature.eClass(); // Ensure it's loaded

                    if (redefinedFeature.getDeclaredName() != null) {
                        output.append("redefines ").append(redefinedFeature.getDeclaredName());
                        isRedefine = true;
                        break;
                    }
                }
            }
        }
        
        // Only output the name if it's not a redefine (redefines uses the original name)
        String name = usage.getDeclaredName();
        if (!isRedefine && name != null) {
            output.append(name);
        }
        

        // Look for typing information (e.g., : Engine)
        for (EObject child : usage.eContents()) {
            if (child instanceof FeatureTyping) {
                System.out.println("       Found FeatureTyping!");
                FeatureTyping typing = (FeatureTyping) child;
                Type type = typing.getType();

                type = (Type) EcoreUtil.resolve(type, usage);


                if (type != null && type.getDeclaredName() != null) {
                    output.append(" : ").append(type.getDeclaredName());
                }
                break; // Only one type per usage
            }
        }


        for (EObject child : usage.eContents()) {
            if (child instanceof FeatureTyping) {
                FeatureTyping typing = (FeatureTyping) child;
                Type type = typing.getType();
                if (type != null) {
                    type.eClass(); // Force proxy resolution
                    String typeName = type.getName();
                    if (typeName != null) {
                        output.append(": ").append(typeName);
                    }
                }
                break;
            }
        }

        // Look for multiplicity information (e.g., [4..6])
        for (EObject child : usage.eContents()) {
            System.out.println("DEBUG Package child type: " + child.eClass().getName());
            // MultiplicityRange might be wrapped in OwningMembership
            if (child instanceof OwningMembership) {
                for (EObject grandchild : child.eContents()) {
                    if (grandchild instanceof MultiplicityRange) {
                        MultiplicityRange mult = (MultiplicityRange) grandchild;
                        
                        // Get lower and upper bounds from the MultiplicityRange's children
                        org.omg.sysml.lang.sysml.Expression lowerBound = null;
                        org.omg.sysml.lang.sysml.Expression upperBound = null;
                        
                        if (mult.getBound().size() > 0) {
                            lowerBound = mult.getBound().get(0);
                        }
                        if (mult.getBound().size() > 1) {
                            upperBound = mult.getBound().get(1);
                        }
                        
                        output.append("[");
                        if (lowerBound instanceof LiteralInteger) {
                            output.append(((LiteralInteger)lowerBound).getValue());
                        }
                        if (upperBound != null && upperBound instanceof LiteralInteger) {
                            output.append("..").append(((LiteralInteger)upperBound).getValue());
                        }
                        output.append("]");
                        break;
                    }
                }
            }
        }

        boolean hasNestedFeatures = false;
        for (EObject child : usage.eContents()) {
            if (child instanceof FeatureMembership) {
                hasNestedFeatures = true;
                break;
            }
        }
        
        if (hasNestedFeatures) {
            output.append(" {\n");
            indentLevel++;
            for (EObject child : usage.eContents()) {
                visit(child);
            }
            indentLevel--;
            writeIndent();
            output.append("}\n");
        } else {
            output.append(";\n");
        }
    }

    private void visitAttributeUsage(AttributeUsage usage) {
        writeIndent();

        if (usage.getDirection() != null) {
            String direction = usage.getDirection().toString().toLowerCase();
            output.append(direction).append(" ");
        }

        output.append("attribute ");
        
        String name = usage.getDeclaredName();
        if (name != null) {
            output.append(name);
        }
        
        // Look for typing information (e.g., : Real)
        for (EObject child : usage.eContents()) {
            if (child instanceof FeatureTyping) {
                FeatureTyping typing = (FeatureTyping) child;
                Type type = typing.getType();
                if (type != null) {
                    // Force proxy resolution
                    type.eClass();
                    if (type.getDeclaredName() != null) {
                        output.append(" : ").append(type.getDeclaredName());
                    }
                }
                break;
            }
        }
        
        // Look for subsetting information (e.g., :> ISQ::mass)
        for (EObject child : usage.eContents()) {
            if (child instanceof Subsetting) {
                Subsetting subsetting = (Subsetting) child;
                Feature subsettedFeature = subsetting.getSubsettedFeature();

                System.err.println("DEBUG Subsetting in attribute '" + usage.getDeclaredName() + "':");
                System.err.println("       subsettedFeature = " + subsettedFeature);

                if (subsettedFeature != null) {
                    // Force proxy resolution
                    if (subsettedFeature.eIsProxy()) {
                        System.err.println("       Feature is a proxy, attempting to resolve...");
                        subsettedFeature = (Feature) EcoreUtil.resolve(subsettedFeature, usage);
                        System.err.println("       After EcoreUtil.resolve: " + subsettedFeature);
                        System.err.println("       Still proxy? " + subsettedFeature.eIsProxy());
                    }
                    subsettedFeature.eClass();
                    // Prefer qualified name (ISQ::torque) over simple name (torque)
                    String subsettedName = getShortenedQualifiedName(subsettedFeature, usage);
                    if (subsettedName == null) {
                        subsettedName = subsettedFeature.getDeclaredName();
                    }

                    System.err.println("       qualifiedName = " + subsettedFeature.getQualifiedName());
                    System.err.println("       declaredName = " + subsettedFeature.getDeclaredName());

                    if (subsettedName != null) {
                        output.append(" :> ").append(subsettedName);
                    }
                }
                break;
            }
        }

        output.append(";\n");
    }

    private void visitReferenceUsage(ReferenceUsage usage) {
        writeIndent();
        
        // Check if we're inside a PortDefinition or InterfaceDefinition
        boolean inPortOrInterface = false;
        EObject parent = usage.eContainer();
        while (parent != null) {
            if (parent instanceof PortDefinition || parent instanceof InterfaceDefinition) {
                inPortOrInterface = true;
                break;
            }
            parent = parent.eContainer();
        }        

        // Check if this is an "end" port (used in interfaces)
        if (usage.isEnd()) {
            output.append("end ");
        }

        // Check for direction (in, out, inout)
        if (usage.getDirection() != null) {
            String direction = usage.getDirection().toString().toLowerCase();
            output.append(direction).append(" ");
            if (!inPortOrInterface) {
                output.append("ref ");
            }
            } else {
                // No direction means we always need explicit 'ref'
                output.append("ref ");
        }
        
        
        String name = usage.getDeclaredName();
        if (name != null) {
            output.append(name);
        }
        
        // Look for typing information
        for (EObject child : usage.eContents()) {
            if (child instanceof FeatureTyping) {
                FeatureTyping typing = (FeatureTyping) child;
                Type type = typing.getType();
                if (type != null) {
                    // Force proxy resolution
                    type.eClass();
                    if (type.getDeclaredName() != null) {
                        output.append(" : ").append(type.getDeclaredName());
                    }
                }
                break;
            }
        }
       
        // Look for subsetting information (e.g., :> ISQ::torque)
        for (EObject child : usage.eContents()) {
            if (child instanceof Subsetting) {
                Subsetting subsetting = (Subsetting) child;
                Feature subsettedFeature = subsetting.getSubsettedFeature();

                System.err.println("DEBUG Subsetting in attribute '" + usage.getDeclaredName() + "':");
                System.err.println("       subsettedFeature = " + subsettedFeature);

                if (subsettedFeature != null) {
                    // Force proxy resolution
                    if (subsettedFeature.eIsProxy()) {
                        System.err.println("       Feature is a proxy, attempting to resolve...");
                        subsettedFeature = (Feature) EcoreUtil.resolve(subsettedFeature, usage);
                        System.err.println("       After EcoreUtil.resolve: " + subsettedFeature);
                        System.err.println("       Still proxy? " + subsettedFeature.eIsProxy());
                    }
                    subsettedFeature.eClass();
                    
                    // Prefer qualified name (ISQ::torque) over simple name (torque)
                    String subsettedName = getShortenedQualifiedName(subsettedFeature, usage);
                    if (subsettedName == null) {
                        subsettedName = subsettedFeature.getDeclaredName();
                    }

                    System.err.println("       qualifiedName = " + subsettedFeature.getQualifiedName());
                    System.err.println("       declaredName = " + subsettedFeature.getDeclaredName());

                    if (subsettedName != null) {
                        output.append(" :> ").append(subsettedName);
                    }
                }
                break;
            }
        }  

        output.append(";\n");
    }

    private void visitOwningMembership(OwningMembership membership) {
        // OwningMembership is a container, just visit its children
        for (EObject child : membership.eContents()) {
            visit(child);
        }
    }
    
    private void visitFeatureMembership(FeatureMembership membership) {
        // FeatureMembership is a container, just visit its children
        for (EObject child : membership.eContents()) {
            visit(child);
        }
    }
    
    private void visitEndFeatureMembership(EndFeatureMembership membership) {
        // EndFeatureMembership contains "end" features in interfaces
        // We need to output "end" keyword before the feature

        System.err.println("DEBUG: visitEndFeatureMembership called");
        System.err.println("       Number of children: " + membership.eContents().size());
        for (EObject child : membership.eContents()) {
            System.err.println("       Child type: " + child.eClass().getName());
        }


        for (EObject child : membership.eContents()) {
            if (child instanceof PortUsage) {
                PortUsage port = (PortUsage) child;
                writeIndent();
                output.append("end ");
                
                String name = port.getDeclaredName();
                if (name != null) {
                    output.append(name);
                }
                
                // Look for typing information
                for (EObject typeChild : port.eContents()) {
                    if (typeChild instanceof FeatureTyping) {
                        FeatureTyping typing = (FeatureTyping) typeChild;
                        Type type = typing.getType();
                        if (type != null) {
                            type.eClass(); // Force proxy resolution
                            if (type.getDeclaredName() != null) {
                                output.append(": ").append(type.getDeclaredName());
                            }
                        }
                        break;
                    }
                }
                
                output.append(";\n");
            } else {
                // For other types, just visit normally
                visit(child);
            }
        }
    }
    
    // Helper method to write indentation
    private void writeIndent() {
        for (int i = 0; i < indentLevel; i++) {
            output.append("    "); // 4 spaces per indent level
        }
    }

    private String getShortenedQualifiedName(Element element, Element context) {
        String fullName = element.getQualifiedName();
        if (fullName == null) {
            return element.getDeclaredName();
        }
        
        // Get the first segment (e.g., "ISQBase" from "ISQBase::mass")
        int firstColon = fullName.indexOf("::");
        if (firstColon == -1) {
            return fullName;
        }
        
        String firstSegment = fullName.substring(0, firstColon);
        String remainder = fullName.substring(firstColon + 2);
        
        // Find containing package
        org.omg.sysml.lang.sysml.Package containingPackage = null;
        EObject current = context;
        while (current != null) {
            if (current instanceof org.omg.sysml.lang.sysml.Package) {
                containingPackage = (org.omg.sysml.lang.sysml.Package) current;
                break;
            }
            current = current.eContainer();
        }
        
        if (containingPackage == null) {
            return fullName;
        }
        
        // Check imports - if we find a parent namespace of firstSegment that's imported,
        // try to use that instead
        for (EObject child : containingPackage.eContents()) {
            if (child instanceof NamespaceImport) {
                NamespaceImport imp = (NamespaceImport) child;
                org.omg.sysml.lang.sysml.Namespace importedNs = imp.getImportedNamespace();
                
                if (importedNs != null) {
                    importedNs.eClass();
                    String importedName = importedNs.getName();
                    
                    // Check if this imported namespace might contain our element
                    // For ISQBase::mass with import ISQ::*, we want to try ISQ::mass
                    if (firstSegment.startsWith(importedName)) {
                        return importedName + "::" + remainder;
                    }
                }
            }
        }
        
        return fullName;
    }

    private void visitFlowUsage(FlowUsage flow) {
        writeIndent();
        output.append("flow ");
        
        // A flow has two ends - source and target
        java.util.List<EndFeatureMembership> ends = new java.util.ArrayList<>();
        for (EObject child : flow.eContents()) {
            if (child instanceof EndFeatureMembership) {
                ends.add((EndFeatureMembership) child);
            }
        }
        
        if (ends.size() != 2) {
            System.err.println("WARNING: Flow has " + ends.size() + " ends, expected 2");
            output.append("/* incomplete flow */;\n");
            return;
        }
        
        // Process first end (source)
        String sourceRef = getFlowEndReference(ends.get(0));
        output.append(sourceRef);
        
        output.append(" to ");
        
        // Process second end (target)
        String targetRef = getFlowEndReference(ends.get(1));
        output.append(targetRef);
        
        output.append(";\n");
    }

    private String getFlowEndReference(EndFeatureMembership endMembership) {
        // EndFeatureMembership contains a FlowEnd which has subsetting info
        for (EObject child : endMembership.eContents()) {
            if (child instanceof FlowEnd) {
                FlowEnd flowEnd = (FlowEnd) child;
                
                // The FlowEnd has subsetting that points to the port
                String portName = null;
                for (EObject featureChild : flowEnd.eContents()) {
                    if (featureChild instanceof ReferenceSubsetting) {
                        ReferenceSubsetting subsetting = (ReferenceSubsetting) featureChild;
                        Feature subsettedFeature = subsetting.getReferencedFeature();
                        if (subsettedFeature != null) {
                            subsettedFeature.eClass(); // Force resolution
                            portName = subsettedFeature.getDeclaredName();
                        }
                    } else if (featureChild instanceof FeatureMembership) {
                        // This contains the nested feature reference (transferredTorque, appliedTorque)
                        for (EObject nestedChild : featureChild.eContents()) {
                            if (nestedChild instanceof ReferenceUsage) {
                                ReferenceUsage refUsage = (ReferenceUsage) nestedChild;
                                String featureName = null;
                                
                                // Look for Redefinition to get the feature name
                                for (EObject refChild : refUsage.eContents()) {
                                    if (refChild instanceof Redefinition) {
                                        Redefinition redef = (Redefinition) refChild;
                                        Feature redefinedFeature = redef.getRedefinedFeature();
                                        if (redefinedFeature != null) {
                                            redefinedFeature.eClass(); // Force resolution
                                            featureName = redefinedFeature.getDeclaredName();
                                        }
                                    }
                                }
                                
                                if (portName != null && featureName != null) {
                                    return portName + "." + featureName;
                                }
                            }
                        }
                    }
                }
            }
        }
        
        return "/* unknown */";
    }

    
}