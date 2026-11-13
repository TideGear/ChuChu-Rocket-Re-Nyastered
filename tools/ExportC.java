import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;

// Exports every function's decompiled C and a symbol/string listing.
// Script arg 0: output directory.
public class ExportC extends GhidraScript {
    @Override
    public void run() throws Exception {
        String outDir = getScriptArgs().length > 0 ? getScriptArgs()[0] : ".";
        new File(outDir).mkdirs();
        String base = currentProgram.getName().replaceAll("[^A-Za-z0-9._-]", "_");
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        try (PrintWriter c = new PrintWriter(new File(outDir, base + ".c"), "UTF-8");
             PrintWriter fl = new PrintWriter(new File(outDir, base + ".functions.txt"), "UTF-8");
             PrintWriter st = new PrintWriter(new File(outDir, base + ".strings.txt"), "UTF-8")) {
            int n = 0;
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                if (monitor.isCancelled()) break;
                fl.println(f.getEntryPoint() + "\t" + f.getBody().getNumAddresses() + "\t" + f.getName());
                if (f.isThunk() || f.isExternal()) continue;
                DecompileResults r = di.decompileFunction(f, 60, monitor);
                if (r.decompileCompleted()) {
                    c.println("// ==== " + f.getName() + " @ " + f.getEntryPoint());
                    c.println(r.getDecompiledFunction().getC());
                }
                n++;
            }
            println("decompiled " + n + " functions");
            DataIterator it = currentProgram.getListing().getDefinedData(true);
            while (it.hasNext()) {
                Data d = it.next();
                if (d.hasStringValue()) st.println(d.getAddress() + "\t" + d.getValue());
            }
        }
    }
}
