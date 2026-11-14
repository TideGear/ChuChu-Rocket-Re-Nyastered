# Mobile texture quality, per piece (measured by tools/measure_assets.py)

696 distinct (family, record) pairs over 12 source folders. For each record the source with the most pixels is the "best"; pieces that exist in one source only have no alternative.

**Caveat:** pieces are matched by record id within a pack family (the UI/background pack, and the character pack), which assumes the builds number the same piece the same way; this was checked by eye on a few records (title, rocket, digits) but not for every record, and records present in several builds with the same size are not compared for content. Ties go to the first folder listed. The Dreamcast textures (named, not numbered) and the GBA graphics are compared by hand for the title/menu/HUD pieces in [provenance.md](provenance.md) and not in this table.

| source folder | textures | records where it is the largest | records only it has |
|---|---|---|---|
| android:com_sega_ccr_1_14_paid | 142 | 82 | 0 |
| android:com_sega_ccr_1_15_paid | 142 | 0 | 0 |
| ios:ChuChu_Rocket_HD_v1_0/ccrpad | 136 | 125 | 0 |
| ios:ChuChu_Rocket_HD_v1_0/ccrphn | 136 | 82 | 0 |
| ios:ChuChu_Rocket_HD_v1_0_OR/ccrpad | 136 | 0 | 0 |
| ios:ChuChu_Rocket_HD_v1_0_OR/ccrphn | 136 | 0 | 0 |
| ios:ChuChu_Rocket__v1_0_2/ccrphn | 133 | 64 | 11 |
| ios:ChuChu_Rocket_v1_0_ORBiT/ccrphn | 136 | 0 | 0 |
| ios:ChuChu_v1_1_os30/ccrphn | 133 | 60 | 25 |
| ios:ChuChu_v1_1_os30/ccrret | 133 | 120 | 109 |
| ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 124 | 50 | 23 |
| ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 124 | 113 | 100 |

## Records where the sources differ in size

| record | sources | best source | best size | smallest pixel count in other sources | gain |
|---|---|---|---|---|---|
| main 4 | 10 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 1024x548 | 518144 | 1.08x |
| main 134 | 3 | android:com_sega_ccr_1_14_paid | 484x322 | 3952 | 39.44x |
| main 144 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 304x97 | 1672 | 17.64x |
| main 147 | 5 | android:com_sega_ccr_1_14_paid | 468x23 | 9996 | 1.08x |
| main 150 | 5 | android:com_sega_ccr_1_14_paid | 264x38 | 4368 | 2.30x |
| main 153 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 184x154 | 5520 | 5.13x |
| main 154 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 200x134 | 9072 | 2.95x |
| main 156 | 5 | android:com_sega_ccr_1_14_paid | 768x240 | 17556 | 10.50x |
| main 165 | 5 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 688x100 | 22140 | 3.11x |
| main 166 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 780x132 | 68800 | 1.50x |
| main 171 | 6 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 464x152 | 3872 | 18.21x |
| main 183 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 692x67 | 2688 | 17.25x |
| main 189 | 3 | android:com_sega_ccr_1_14_paid | 208x52 | 8284 | 1.31x |
| main 191 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 1008x127 | 1672 | 76.56x |
| main 192 | 3 | android:com_sega_ccr_1_14_paid | 236x78 | 1672 | 11.01x |
| main 195 | 3 | android:com_sega_ccr_1_14_paid | 240x163 | 10764 | 3.63x |
| main 197 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 368x33 | 7128 | 1.70x |
| main 200 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 340x40 | 10032 | 1.36x |
| main 203 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 336x31 | 5520 | 1.89x |
| main 206 | 5 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 768x240 | 13572 | 13.58x |
| main 224 | 3 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 204x49 | 5328 | 1.88x |
| main 226 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 244x65 | 8120 | 1.95x |
| main 227 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 468x23 | 4368 | 2.46x |
| main 229 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 204x49 | 1240 | 8.06x |
| main 230 | 3 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 228x62 | 11968 | 1.18x |
| main 232 | 7 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 340x39 | 4368 | 3.04x |
| main 235 | 7 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 416x35 | 7068 | 2.06x |
| main 238 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 428x36 | 8260 | 1.87x |
| main 241 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 1024x67 | 1200 | 57.17x |
| main 255 | 4 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 892x63 | 37632 | 1.49x |
| main 259 | 6 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 692x67 | 7560 | 6.13x |
| main 262 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 324x42 | 7568 | 1.80x |
| main 265 | 6 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 892x63 | 1120 | 50.17x |
| main 268 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 896x42 | 6708 | 5.61x |
| main 269 | 2 | ios:ChuChu_v1_1_os30/ccrphn | 892x63 | 46364 | 1.21x |
| main 272 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 288x43 | 12144 | 1.02x |
| main 273 | 2 | ios:ChuChu_v1_1_os30/ccrphn | 692x67 | 46008 | 1.01x |
| main 275 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 324x42 | 13600 | 1.00x |
| main 277 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 680x134 | 1120 | 81.36x |
| main 278 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 312x44 | 10416 | 1.32x |
| main 281 | 5 | ios:ChuChu_v1_1_os30/ccrphn | 680x134 | 13572 | 6.71x |
| main 285 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 340x40 | 11808 | 1.15x |
| main 286 | 3 | ios:ChuChu_v1_1_os30/ccrphn | 368x33 | 7568 | 1.60x |
| main 288 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 328x43 | 10416 | 1.35x |
| main 289 | 3 | ios:ChuChu_v1_1_os30/ccrphn | 340x40 | 1120 | 12.14x |
| main 291 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 348x39 | 13272 | 1.02x |
| main 292 | 3 | ios:ChuChu_v1_1_os30/ccrphn | 336x31 | 6240 | 1.67x |
| main 294 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 924x41 | 13260 | 2.86x |
| main 295 | 3 | ios:ChuChu_v1_1_os30/ccrphn | 348x39 | 7912 | 1.72x |
| main 297 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 424x37 | 14560 | 1.08x |
| main 298 | 6 | ios:ChuChu_v1_1_os30/ccrphn | 424x34 | 7052 | 2.04x |
| main 300 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 548x73 | 15408 | 2.60x |
| main 301 | 6 | ios:ChuChu_v1_1_os30/ccrphn | 424x37 | 1064 | 14.74x |
| main 303 | 3 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 1024x37 | 7480 | 5.07x |
| main 304 | 7 | ios:ChuChu_v1_1_os30/ccrphn | 548x73 | 6080 | 6.58x |
| main 307 | 7 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 924x41 | 7912 | 4.79x |
| main 310 | 6 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 452x71 | 7052 | 4.55x |
| main 311 | 4 | ios:ChuChu_v1_1_os30/ccrphn | 416x35 | 11360 | 1.28x |
| main 313 | 6 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 592x311 | 1064 | 173.04x |
| main 314 | 4 | ios:ChuChu_v1_1_os30/ccrphn | 428x36 | 14104 | 1.09x |
| main 316 | 3 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 560x77 | 6080 | 7.09x |
| main 317 | 5 | ios:ChuChu_v1_1_os30/ccrphn | 1024x37 | 13260 | 2.86x |
| main 320 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 924x41 | 12384 | 3.06x |
| main 321 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 220x175 | 13260 | 2.90x |
| main 323 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 428x36 | 13608 | 1.13x |
| main 324 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 148x111 | 14560 | 1.13x |
| main 325 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 308x102 | 1064 | 29.53x |
| main 326 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 560x77 | 13728 | 3.14x |
| main 327 | 4 | ios:ChuChu_v1_1_os30/ccrphn | 428x36 | 6956 | 2.22x |
| main 328 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 616x203 | 16428 | 7.61x |
| main 330 | 5 | ios:ChuChu_v1_1_os30/ccrphn | 560x77 | 2516 | 17.14x |
| main 333 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 1008x86 | 12384 | 7.00x |
| main 334 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 240x95 | 2516 | 9.06x |
| main 336 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 312x44 | 13608 | 1.01x |
| main 337 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 1024x218 | 13608 | 16.40x |
| main 339 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 896x42 | 13728 | 2.74x |
| main 342 | 3 | android:com_sega_ccr_1_14_paid | 992x80 | 37632 | 2.11x |
| main 343 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 1008x86 | 12384 | 7.00x |
| main 346 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 1016x214 | 12384 | 17.56x |
| main 347 | 3 | android:com_sega_ccr_1_14_paid | 992x80 | 12384 | 6.41x |
| main 349 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 312x44 | 13608 | 1.01x |
| main 352 | 4 | android:com_sega_ccr_1_14_paid | 992x80 | 13728 | 5.78x |
| main 353 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 1008x86 | 13728 | 6.31x |
| main 355 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 1004x199 | 37632 | 5.31x |
| main 356 | 2 | ios:ChuChu_v1_1_os30/ccrphn | 896x42 | 12384 | 3.04x |
| main 359 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 324x42 | 11808 | 1.15x |
| main 362 | 4 | android:com_sega_ccr_1_14_paid | 992x80 | 13728 | 5.78x |
| main 363 | 4 | ios:ChuChu_v1_1_os30/ccrphn | 324x42 | 4096 | 3.32x |
| main 365 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 896x42 | 13272 | 2.84x |
| main 366 | 4 | ios:ChuChu_v1_1_os30/ccrphn | 312x44 | 3696 | 3.71x |
| main 369 | 5 | ios:ChuChu_v1_1_os30/ccrphn | 896x42 | 2376 | 15.84x |
| main 372 | 5 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 328x43 | 6216 | 2.27x |
| main 373 | 3 | ios:ChuChu_v1_1_os30/ccrphn | 288x41 | 2376 | 4.97x |
| main 375 | 5 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 328x43 | 4096 | 3.44x |
| main 376 | 3 | ios:ChuChu_v1_1_os30/ccrphn | 328x43 | 6512 | 2.17x |
| main 378 | 5 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 924x41 | 8272 | 4.58x |
| main 379 | 3 | ios:ChuChu_v1_1_os30/ccrphn | 316x42 | 4096 | 3.24x |
| main 381 | 6 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 612x75 | 31620 | 1.45x |
| main 382 | 4 | ios:ChuChu_v1_1_os30/ccrphn | 924x41 | 11360 | 3.33x |
| main 385 | 6 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 604x57 | 3780 | 9.11x |
| main 388 | 4 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 328x43 | 672 | 20.99x |
| main 389 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 640x71 | 14104 | 3.22x |
| main 391 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 924x41 | 1980 | 19.13x |
| main 393 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 772x62 | 1980 | 24.17x |
| main 394 | 3 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 924x41 | 33792 | 1.12x |
| main 395 | 2 | ios:ChuChu_v1_1_os30/ccrphn | 924x41 | 11360 | 3.33x |
| main 398 | 4 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 148x111 | 2176 | 7.55x |
| main 401 | 6 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 996x133 | 6956 | 19.04x |
| main 404 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 924x41 | 2516 | 15.06x |
| main 407 | 6 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 1008x86 | 1496 | 57.95x |
| main 408 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 620x71 | 16428 | 2.68x |
| main 410 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 424x32 | 3536 | 3.84x |
| main 412 | 4 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 1008x86 | 16428 | 5.28x |
| main 413 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 240x68 | 3536 | 4.62x |
| main 416 | 7 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 780x66 | 1496 | 34.41x |
| main 422 | 7 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 1008x86 | 3536 | 24.52x |
| main 425 | 5 | android:com_sega_ccr_1_14_paid | 84x109 | 2760 | 3.32x |
| main 427 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 1008x86 | 44020 | 1.97x |
| main 428 | 5 | android:com_sega_ccr_1_14_paid | 84x109 | 3536 | 2.59x |
| main 431 | 8 | ios:ChuChu_v1_1_os30/ccrphn | 1008x86 | 9156 | 9.47x |
| main 437 | 7 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 1008x86 | 4096 | 21.16x |
| main 440 | 6 | android:com_sega_ccr_1_14_paid | 84x109 | 3696 | 2.48x |
| main 443 | 6 | android:com_sega_ccr_1_14_paid | 484x76 | 2376 | 15.48x |
| main 446 | 5 | ios:ChuChu_v1_1_os30/ccrphn | 1008x86 | 6512 | 13.31x |
| main 447 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 512x78 | 4096 | 9.75x |
| main 449 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 484x76 | 4096 | 8.98x |
| main 450 | 3 | android:com_sega_ccr_1_14_paid | 440x91 | 3696 | 10.83x |
| main 451 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 584x77 | 4096 | 10.98x |
| main 453 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 172x50 | 2376 | 3.62x |
| main 454 | 3 | android:com_sega_ccr_1_14_paid | 220x81 | 3696 | 4.82x |
| main 455 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 556x82 | 3780 | 12.06x |
| main 456 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 152x47 | 6512 | 1.10x |
| main 457 | 3 | android:com_sega_ccr_1_14_paid | 60x74 | 2376 | 1.87x |
| main 459 | 6 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 1024x149 | 4096 | 37.25x |
| main 460 | 3 | ios:ChuChu_v1_1_os30/ccrphn | 176x37 | 4440 | 1.47x |
| main 462 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 204x106 | 8272 | 2.61x |
| main 463 | 3 | android:com_sega_ccr_1_14_paid | 60x74 | 4096 | 1.08x |
| main 465 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 124x177 | 5200 | 4.22x |
| main 466 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 508x78 | 4440 | 8.92x |
| main 468 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 260x58 | 2176 | 6.93x |
| main 469 | 3 | ios:ChuChu_v1_1_os30/ccrphn | 124x177 | 3960 | 5.54x |
| main 471 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 440x177 | 672 | 115.89x |
| main 472 | 3 | android:com_sega_ccr_1_14_paid | 60x66 | 3780 | 1.05x |
| main 474 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 556x82 | 9408 | 4.85x |
| main 475 | 3 | android:com_sega_ccr_1_14_paid | 280x34 | 672 | 14.17x |
| main 477 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 60x33 | 1496 | 1.32x |
| main 478 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 1024x148 | 9408 | 16.11x |
| main 480 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 488x133 | 3536 | 18.36x |
| main 481 | 3 | android:com_sega_ccr_1_14_paid | 484x382 | 1980 | 93.38x |
| main 484 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 484x149 | 64904 | 1.11x |
| main 485 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 508x78 | 21608 | 1.83x |
| main 488 | 4 | ios:ChuChu_v1_1_os30/ccrphn | 484x149 | 21608 | 3.34x |
| main 489 | 6 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 584x77 | 3536 | 12.72x |
| main 492 | 3 | android:com_sega_ccr_1_14_paid | 488x65 | 19008 | 1.67x |
| main 493 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 556x82 | 2176 | 20.95x |
| main 495 | 3 | android:com_sega_ccr_1_14_paid | 452x63 | 9156 | 3.11x |
| main 497 | 6 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 1024x149 | 2176 | 70.12x |
| main 498 | 3 | android:com_sega_ccr_1_14_paid | 448x66 | 9156 | 3.23x |
| main 500 | 4 | ios:ChuChu_v1_1_os30/ccrphn | 424x32 | 9520 | 1.43x |
| main 501 | 3 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 84x109 | 4324 | 2.12x |
| main 503 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 132x126 | 16320 | 1.02x |
| main 504 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 508x74 | 1008 | 37.29x |
| main 506 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 484x382 | 1496 | 123.59x |
| main 507 | 3 | android:com_sega_ccr_1_14_paid | 260x109 | 9156 | 3.10x |
| main 508 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 592x78 | 3536 | 13.06x |
| main 510 | 3 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 84x109 | 8004 | 1.14x |
| main 512 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 564x76 | 3536 | 12.12x |
| main 513 | 3 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 484x76 | 15200 | 2.42x |
| main 514 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 124x126 | 3536 | 4.42x |
| main 516 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 1008x149 | 102960 | 1.46x |
| main 517 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 488x65 | 9156 | 3.46x |
| main 520 | 5 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 440x91 | 9156 | 4.37x |
| main 523 | 6 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 508x74 | 9156 | 4.11x |
| main 524 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 220x81 | 9156 | 1.95x |
| main 526 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 84x109 | 4324 | 2.12x |
| main 527 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 592x78 | 9156 | 5.04x |
| main 529 | 4 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 84x109 | 1008 | 9.08x |
| main 530 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 292x74 | 9156 | 2.36x |
| main 532 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 260x109 | 9156 | 3.10x |
| main 533 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 292x74 | 9156 | 2.36x |
| main 535 | 6 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 1008x149 | 8004 | 18.76x |
| main 536 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 292x74 | 9156 | 2.36x |
| main 539 | 3 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 292x73 | 8600 | 2.48x |
| main 542 | 8 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 508x74 | 7144 | 5.26x |
| main 545 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrphn | 780x132 | 5640 | 18.26x |
| main 546 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 592x78 | 8600 | 5.37x |
| main 548 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 204x106 | 16632 | 1.30x |
| main 551 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 484x382 | 5200 | 35.56x |
| main 554 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 1008x149 | 15080 | 9.96x |
| main 561 | 3 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 264x198 | 15080 | 3.47x |
| main 562 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 488x65 | 8624 | 3.68x |
| main 565 | 4 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 452x63 | 17820 | 1.60x |
| main 568 | 5 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 448x66 | 6336 | 4.67x |
| main 571 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 968x305 | 4324 | 68.28x |
| main 574 | 3 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 292x74 | 1008 | 21.44x |
| main 577 | 3 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 260x109 | 21608 | 1.31x |
| main 580 | 3 | ios:ChuChu_v1_1_os30/ccrphn | 292x74 | 8004 | 2.70x |
| main 583 | 5 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 968x305 | 15200 | 19.42x |
| main 586 | 3 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrphn | 780x132 | 9520 | 10.82x |
| main 589 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 132x126 | 9520 | 1.75x |
| main 592 | 3 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 484x382 | 4324 | 42.76x |
| main 595 | 4 | ios:ChuChu_Rocket_HD_v1_0/ccrpad | 968x305 | 14824 | 19.92x |
| main 603 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 488x65 | 15624 | 2.03x |
| main 606 | 2 | ios:ChuChu_v1_1_os30/ccrphn | 488x65 | 28476 | 1.11x |
| main 609 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 448x66 | 28476 | 1.04x |
| main 612 | 2 | ios:ChuChu_v1_1_os30/ccrphn | 448x66 | 4324 | 6.84x |
| main 615 | 2 | ios:ChuChu_v1_1_os30/ccrphn | 92x47 | 1008 | 4.29x |
| main 618 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 260x109 | 1008 | 28.12x |
| main 621 | 2 | ios:ChuChu_v1_1_os30/ccrphn | 260x109 | 8004 | 3.54x |
| main 624 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 200x76 | 8004 | 1.90x |
| main 627 | 2 | ios:ChuChu_Rocket__v1_0_2/ccrphn | 780x132 | 15200 | 6.77x |
| ret 4 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 1024x536 | 518144 | 1.06x |
| ret 438 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 1004x199 | 10816 | 18.47x |
| ret 480 | 2 | ios:ChuChu_v1_1_os30/ccrret | 1024x352 | 51480 | 7.00x |
| ret 551 | 2 | ios:ChuChu_v1_1_os30/ccrret | 780x66 | 36120 | 1.43x |
| ret 555 | 2 | ios:ChuChu_v1_1_os30/ccrret | 1012x189 | 38184 | 5.01x |
| ret 566 | 2 | ios:ChuChu_v1_1_os30/ccrret | 516x70 | 28968 | 1.25x |
| ret 584 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 516x74 | 36120 | 1.06x |
| ret 588 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 588x78 | 38184 | 1.20x |
| ret 592 | 2 | ios:ChuChu_v1_1_os30/ccrret | 1000x135 | 42812 | 3.15x |
| ret 648 | 2 | ios:ChuChu_v1_1_os30/ccrret | 1024x140 | 6336 | 22.63x |
| ret 663 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 968x305 | 41952 | 7.04x |
| ret 732 | 2 | ios:ChuChu_v1_1_os30/ccrret | 968x305 | 24192 | 12.20x |
| ret 756 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 124x66 | 6560 | 1.25x |
| ret 759 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 424x32 | 13104 | 1.04x |
| ret 762 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 200x264 | 8296 | 6.36x |
| ret 789 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 156x200 | 6800 | 4.59x |
| ret 792 | 2 | ios:ChuChu_v1_1_os30/ccrret | 968x261 | 31200 | 8.10x |
| ret 813 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 496x304 | 33792 | 4.46x |
| ret 820 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 660x240 | 13568 | 11.67x |
| ret 827 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 512x132 | 3888 | 17.38x |
| ret 842 | 2 | ios:ChuChu_v1_1_os30/ccrret | 424x176 | 67584 | 1.10x |
| ret 847 | 2 | ios:SEGA_ChuChu_Rocket_v1_1_/ccrret | 512x132 | 31200 | 2.17x |
| ret 891 | 2 | ios:ChuChu_v1_1_os30/ccrret | 496x304 | 28476 | 5.30x |

Records identical in size in all sources that have them: 194 of 428.
