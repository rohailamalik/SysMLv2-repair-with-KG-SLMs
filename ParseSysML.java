import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.EPackage;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.xtext.resource.XtextResourceSet;
import com.google.inject.Injector;
import org.omg.kerml.xtext.KerMLStandaloneSetup;
import org.omg.kerml.xtext.xmi.KerMLxStandaloneSetup;
import org.omg.sysml.xtext.xmi.SysMLxStandaloneSetup;
import org.omg.sysml.xtext.SysMLStandaloneSetup;
import org.omg.sysml.lang.sysml.SysMLPackage;
import org.omg.sysml.lang.sysml.Element;
import org.omg.sysml.lang.sysml.Redefinition;
import org.omg.sysml.lang.sysml.PartDefinition;
import org.eclipse.emf.common.util.TreeIterator;
import org.eclipse.emf.ecore.util.EcoreUtil;
import org.omg.sysml.lang.sysml.util.SysMLLibraryUtil;
import org.omg.sysml.interactive.SysMLInteractive;


public class ParseSysML {
    public static void main(String[] args) throws Exception {
        EPackage.Registry.INSTANCE.put(SysMLPackage.eNS_URI, SysMLPackage.eINSTANCE);
        KerMLStandaloneSetup.doSetup();
        KerMLxStandaloneSetup.doSetup();
        SysMLxStandaloneSetup.doSetup();
        Injector injector = new SysMLStandaloneSetup().createInjectorAndDoEMFRegistration();
        
        
        SysMLInteractive interactive = SysMLInteractive.getInstance();
        String libraryPath = "C:/Haitham/sysml-test/sysml.library";
        
        interactive.loadLibrary(libraryPath);
        System.out.println("Libraries loaded from: " + libraryPath);

        ResourceSet resourceSet = interactive.getResourceSet();
        
        System.out.println("\nResources in library set: " + resourceSet.getResources().size());        

        URI uri = URI.createFileURI("C:/Haitham/sysml-test/test2.sysml");
        Resource resource = resourceSet.getResource(uri, true);

        if (!resource.getErrors().isEmpty()) {
            System.err.println("Parse errors:");
            resource.getErrors().forEach(System.err::println);
            return;
        }
        

        // check whats loaded 
        System.out.println("\n=== LOADED RESOURCES ===");
        for (Resource r : resourceSet.getResources()) {
            System.out.println("Resource: " + r.getURI());
            System.out.println("  Contents: " + r.getContents().size() + " root elements");
            if (!r.getContents().isEmpty()) {
                EObject root = r.getContents().get(0);
                System.out.println("  Root type: " + root.eClass().getName());
            }
        }

        System.out.println("\n=== RESOLVING ALL PROXIES ===");
        System.out.println("Before: " + resourceSet.getResources().size() + " resources");
        EcoreUtil.resolveAll(resourceSet);
        System.out.println("After: " + resourceSet.getResources().size() + " resources");
        
        // Check if there are unresolved proxies
        for (Resource r : resourceSet.getResources()) {
            if (!r.getErrors().isEmpty()) {
                System.err.println("Errors in " + r.getURI() + ": " + r.getErrors());
            }
        }


        System.out.println("=== ORIGINAL AST ===");
        printAST(resource.getContents().get(0), 0);
    
        // Use our custom serializer
        System.out.println("\n=== CUSTOM SERIALIZED SYSML CODE ===");
        SysMLSerializer serializer = new SysMLSerializer();
        String serialized = serializer.serialize(resource.getContents().get(0));
        System.out.println(serialized);
    }
    
    static void printAST(EObject node, int depth) {
        String indent = "  ".repeat(depth);
        String name = "";
        
        if (node instanceof Element) {
            Element element = (Element) node;
            if (element.getDeclaredName() != null) {
                name = " [name: " + element.getDeclaredName() + "]";
            }
        }
        
        if (node instanceof org.omg.sysml.lang.sysml.Subsetting) {
            org.omg.sysml.lang.sysml.Subsetting sub = (org.omg.sysml.lang.sysml.Subsetting) node;
            org.omg.sysml.lang.sysml.Feature target = sub.getSubsettedFeature();
            System.out.println(indent + "  >>> Subsetting target: " + target);
            System.out.println(indent + "  >>> Is proxy? " + (target != null ? target.eIsProxy() : "null"));
            if (target != null && !target.eIsProxy()) {
                System.out.println(indent + "  >>> Target name: " + target.getQualifiedName());
            }
        }


        System.out.println(indent + node.eClass().getName() + name);
        
        for (EObject child : node.eContents()) {
            printAST(child, depth + 1);
        }
    }
}