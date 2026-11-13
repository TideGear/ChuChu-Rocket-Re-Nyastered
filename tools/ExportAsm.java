import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.regex.*;

// args: outFile, comma-separated function name prefixes
// Dumps instructions of matching functions; for each data reference prints the 4 bytes at the target as hex/int/float.
public class ExportAsm extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        String[] prefixes = java.util.Arrays.copyOfRange(a, 1, a.length);
        try (PrintWriter w = new PrintWriter(new File(a[0]), "UTF-8")) {
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                boolean hit = false; for (String p : prefixes) { if (p.startsWith("0x")) { if (f.getEntryPoint().getOffset() == Long.parseLong(p.substring(2), 16)) hit = true; } else if (f.getName().startsWith(p)) hit = true; } if (!hit) continue;
                w.println("==== " + f.getName() + " @ " + f.getEntryPoint());
                InstructionIterator it = currentProgram.getListing().getInstructions(f.getBody(), true);
                while (it.hasNext()) {
                    Instruction ins = it.next();
                    StringBuilder sb = new StringBuilder();
                    sb.append(ins.getAddress()).append("  ").append(ins.toString());
                    for (Reference r : ins.getReferencesFrom()) {
                        if (r.getReferenceType().isData() || r.getReferenceType().isRead()) {
                            Address t = r.getToAddress();
                            try {
                                int v = currentProgram.getMemory().getInt(t);
                                sb.append("   ; [").append(t).append("]=0x").append(Integer.toHexString(v))
                                  .append(" int=").append(v).append(" float=").append(Float.intBitsToFloat(v));
                            } catch (Exception e) { /* unmapped */ }
                        }
                    }
                    w.println(sb);
                }
                w.println();
            }
        }
    }
}
