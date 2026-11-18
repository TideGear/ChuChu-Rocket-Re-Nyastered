import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

// Import MANATEE.DRV without its 32-byte SDRV header, at base 0, ARM:LE:32:v4.
// Known entry points in the tested USA driver's ARM image.
public class SeedDcSound extends GhidraScript {
    public void run() throws Exception {
        long[] entries = {0x100, 0x230, 0x244, 0x1c30, 0x87f8};
        for (long entry : entries) {
            Address address = toAddr(entry);
            addEntryPoint(address);
            disassemble(address);
            createFunction(address, null);
        }
    }
}
