# Rules spec: arrows (draft, iOS 1.1.2 `AR_*`, ARM Thumb-2 disassembly)

Per-player arrow storage: 4 players x (4-byte header + 3 slots x 24 bytes) = 76 bytes per player.
Slot fields: +0 direction, +1 hit counter, +4 time-to-live in frames (-1 = empty), +8/+0xA grid x/y (shorts). Header byte +5 = ring index (0..2).

- **Placement** (`AR_PutArrowLcl`, local/puzzle path): refused if the target cell's collision word has any of the object bits `0xF00`
  set (rocket, hole, etc.). If the player already has an arrow on that cell, only its direction is replaced. Otherwise the slot at the ring
  index is freed first (so the 4th arrow replaces the oldest, round robin over 3 slots), then the new arrow is written with
  **time-to-live 0x258 = 600 frames**, hit counter 0, and the ring index advances (wraps after 2).
- **Battle placement** (`AR_PutArrow`): additionally checks `cell & 0x700` (cells holding another arrow cannot be taken unless it is the
  local player's own); each player's slots are compared by expiry time and the one expiring first is replaced.
- **Expiry** (`AR_ArrowExeLcl`, once per frame): every used slot's TTL is decremented; at 0 the arrow is deleted (`AR_DeleteArrow`).
  The fade-out visual is separate (draw routines).
- **Cat strike** (`AR_CatHitArrow` -> `AR_StrikeArrow`): a cat arriving at a cell with an arrow increments the arrow's hit counter; when the
  counter exceeds 1 (second strike) the arrow is deleted. In game types 3 and 4 (battle) only the 4-player table is searched; other types
  search the single-player arrow table.
- Cell collision bit `0x800` = arrow present (set by `FI_CollisionEntryArrow`, cleared by `FI_CollisionCancelArrow`);
  low 2 bits = arrow direction (`FI_CheckAndCorrectAngle` uses `flags & 3`).

Open: TTL fade timing for rendering, the puzzle-mode arrow limit (stage arrow counts), mice passing over arrows (no damage).
