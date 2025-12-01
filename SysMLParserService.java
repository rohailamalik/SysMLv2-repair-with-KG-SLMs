import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.util.EcoreUtil;
import org.omg.kerml.xtext.KerMLStandaloneSetup;
import org.omg.kerml.xtext.xmi.KerMLxStandaloneSetup;
import org.omg.sysml.xtext.xmi.SysMLxStandaloneSetup;
import org.omg.sysml.lang.sysml.SysMLPackage;
import org.omg.sysml.interactive.SysMLInteractive;
import org.eclipse.emf.ecore.EPackage;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Paths;
import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;

public class SysMLParserService {

    private static SysMLInteractive interactive;
    private static ResourceSet resourceSet;
    private static ObjectMapper mapper = new ObjectMapper();

    static {
        
        // One-time initialization
        EPackage.Registry.INSTANCE.put(SysMLPackage.eNS_URI, SysMLPackage.eINSTANCE);
        KerMLStandaloneSetup.doSetup();
        KerMLxStandaloneSetup.doSetup();
        SysMLxStandaloneSetup.doSetup();

        interactive = SysMLInteractive.getInstance();
        
        Path base = Paths.get(System.getProperty("user.dir"));  // working directory
        Path lib  = base.resolve("sysml.library");
        interactive.loadLibrary(lib.toString());

        resourceSet = interactive.getResourceSet();
        EcoreUtil.resolveAll(resourceSet);
        
    }
    
    public static class ParseException extends RuntimeException {
        public ParseException(String message) {
            super(message);
        }
    }

    // Parse a SysML code string
    public static String parseString(String sysmlText) throws Exception {
        Resource res = resourceSet.createResource(URI.createURI("inmemory:/temp.sysml"));
        res.load(new ByteArrayInputStream(sysmlText.getBytes(StandardCharsets.UTF_8)), null);
        return serializeResource(res);
    }

    // Parse a SysML file from the given file path
    public static String parseFile(String filePath) throws Exception {
        URI uri = URI.createFileURI(new java.io.File(filePath).getAbsolutePath());
        Resource res = resourceSet.getResource(uri, true);
        return serializeResource(res);
    }


    private static String serializeResource(Resource resource) throws Exception {
        if (!resource.getErrors().isEmpty()) {
            throw new ParseException("Parse errors: " + resource.getErrors());
        }
        
        EObject root = resource.getContents().get(0);
        Map<String, Object> jsonAST = toJson(root);
        return mapper.writeValueAsString(jsonAST);
    }


    private static Map<String, Object> toJson(EObject node) {
        Map<String, Object> obj = new LinkedHashMap<>();
        obj.put("type", node.eClass().getName());

        if (node instanceof org.omg.sysml.lang.sysml.Element) {
            org.omg.sysml.lang.sysml.Element el = (org.omg.sysml.lang.sysml.Element) node;
            if (el.getDeclaredName() != null)
                obj.put("name", el.getDeclaredName());
        }

        List<Map<String, Object>> children = new ArrayList<>();
        for (EObject child : node.eContents()) {
            children.add(toJson(child));
        }
        if (!children.isEmpty()) {
            obj.put("children", children);
        }
        return obj;
    }
}
