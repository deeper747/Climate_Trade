// EU ETS product benchmarks (BMg, Column B) from EU Implementing Regulation 2025/2620, Annex I.
// Values in tCO2e per metric ton of product.
// Keys: trKey(cn) + (route ? ":" + route : "")
// Many integer values in the source CSV had "0," prefix stripped; correct values restored here.

// CBAM factor = fraction of benchmark still granted as free allocation (Article 10a, Directive 2003/87/EC).
// CBAM cost formula: max(0, DV×(1+markup) − Benchmark × CBAM_FACTOR[year]) × ETS × EUR_USD
// As CBAM_FACTOR falls from 97.5% → 0%, the benchmark credit shrinks and the charge grows.
export const CBAM_FACTOR = {
  2026: 0.975,  // 97.5% free allocation remaining → 2.5% charged net
  2027: 0.95,   // 95% → 5%
  2028: 0.90,   // 90% → 10%
  2029: 0.775,  // 77.5% → 22.5%
  2030: 0.515,  // 51.5% → 48.5%
  2031: 0.39,   // 39% → 61%
  2032: 0.265,  // 26.5% → 73.5%
  2033: 0.14,   // 14% → 86%
  2034: 0.0,    // 0% → 100% (no CBAM factor from 2034 = no free allocation)
  2035: 0.0,
};

export const BENCHMARKS = {
  // Cement
  "25070080:A":  0.666,   // Calcined clay / kaolinic clays
  "25231000:A":  0.666,   // Grey clinker
  "25231000:B":  0.859,   // White clinker
  "25232100":    0.859,   // White Portland cement
  "25232900":    0.666,   // Grey Portland cement
  "25233000":    0.717,   // Aluminous cement (route 1 value)
  "25239000:A":  0.666,   // Grey hydraulic cements
  "25239000:B":  0.847,   // White hydraulic cements
  // Hydrogen
  "28041000":    5.089,   // Hydrogen
  // Fertilizers
  "28080000":    0.582,   // Nitric acid
  "28141000":    1.522,   // Anhydrous ammonia
  "28142000":    0.457,   // Ammonia in aqueous solution
  "28342100":    0.626,   // Potassium nitrate
  "31021012":    0.304,   // Urea aq. sol. 31.8–33.2%
  "31021015":    0.503,   // Urea aq. sol. 33.2–55%
  "31021019":    0.902,   // Urea >45%N solid
  "31021090":    0.882,   // Urea ≤45%N
  "31022100":    0.414,   // Ammonium sulphate
  "31022900":    0.566,   // Double salts ammonium sulphate/nitrate
  "31023010":    0.508,   // Ammonium nitrate aqueous
  "31023090":    0.767,   // Ammonium nitrate solid
  "31024010":    0.688,   // AN+CaCO₃ ≤28%N
  "31024090":    0.688,   // AN+CaCO₃ >28%N
  "31025000":    0.693,   // Sodium nitrate (avg routes 1/2: 0.701, 0.685)
  "31026000":    0.633,   // Calcium nitrate/AN mix
  "31028000":    0.625,   // UAN solution
  "31029000":    0.847,   // Other N fertilizers
  "31051000":    0.376,   // NPK packaged
  "31052010":    0.434,   // NPK >10%N
  "31052090":    0.319,   // NPK ≤10%N
  "31053000":    0.339,   // DAP
  "31054000":    0.173,   // MAP
  "31055100":    0.548,   // NP nitrates+phosphates
  "31055900":    0.391,   // NP other
  "31059020":    0.476,   // NK >10%N
  "31059080":    0.248,   // NK ≤10%N
  // Iron & Steel — no specific route
  "26011200":    0.086,   // Agglomerated iron ores
  "7201":        1.210,   // Pig iron
  "720211":      1.319,   // Ferro-manganese >2%C (avg routes 1/2: 1.361, 1.277)
  "720241":      1.124,   // Ferro-chromium (avg routes 1/2: 1.142, 1.106)
  "72026000":    2.343,   // Ferro-nickel (avg routes 1/2: 2.390, 2.295)
  "7203":        0.397,   // DRI products
  "72181000":    1.400,   // Stainless steel ingots (avg routes 1/2: 1.419, 1.381)
  "72191100":    1.170,   // SS flat-rolled ≥600mm HR (avg: 1.189, 1.151)
  "72193100":    1.250,   // SS flat-rolled ≥600mm CR (avg: 1.270, 1.230)
  "7221":        1.206,   // SS bars/rods HR coils (avg: 1.225, 1.187)
  "722300":      1.206,   // SS wire (avg: 1.225, 1.187)
  "730300":      1.484,   // Cast iron tubes/pipes
  "73072100":    1.154,   // SS flanges (avg: 1.173, 1.135)
  // Iron & Steel — route C (BF-BOF)
  "7205:C":      1.288,   // Granules/powders of pig iron
  "72061000:C":  1.288,   // Steel ingots
  "7208:C":      1.370,   // HR flat-rolled ≥600mm
  "7209:C":      1.458,   // CR flat-rolled ≥600mm
  "7210:C":      1.491,   // Flat-rolled ≥600mm coated
  "72111300:C":  1.370,   // Wide flats 150–600mm
  "7212:C":      1.491,   // Flat-rolled <600mm coated
  "7213:C":      1.364,   // Bars and rods HR coils
  "72142000:C":  1.364,   // Rebars
  "7215:C":      1.364,   // Bars and rods cold-formed
  "7216:C":      1.364,   // Angles, shapes, sections
  "721710:C":    1.364,   // Wire uncoated
  "721720:C":    1.397,   // Wire zinc-coated
  "72251100:C":  1.779,   // Si-electrical steel grain-oriented ≥600mm
  "7301:C":      1.458,   // Sheet piling
  "7302:C":      1.383,   // Railway track material
  "730419:C":    1.383,   // Seamless line pipe non-SS
  "730439:C":    1.383,   // Seamless circular tubes HR non-SS
  "7305:C":      1.458,   // Large-diameter welded pipes
  "73061900:C":  1.458,   // Welded line pipe non-SS
  "73063080:C":  1.491,   // Welded tubes 168–406mm non-SS
  "73079100:C":  1.383,   // Flanges non-SS
  "7308:C":      1.491,   // Steel structures
  "7309:C":      1.491,   // Steel tanks >300L
  "7310:C":      1.491,   // Steel tanks ≤300L
  "731100:C":    1.364,   // Steel containers compressed gas
  "731815:C":    1.364,   // Screws and bolts
  "731816:C":    1.364,   // Nuts
  "73182200:C":  1.364,   // Washers
  "73182300:C":  1.364,   // Rivets
  "73269098:C":  1.491,   // Articles of iron/steel NES
  // Iron & Steel — route F (alloy steel primary, avg grades 1/2)
  "722410:F":    1.724,   // Alloy steel ingots (F: 1.807/1.640 avg)
  "722530:F":    1.493,   // Alloy steel HR ≥600mm coils (F: 1.577/1.409 avg)
  "722550:F":    1.586,   // Alloy steel CR ≥600mm (F: 1.673/1.499 avg)
  // Aluminum — route K (primary)
  "7601:K":      1.423,
  "7603:K":      1.506,
  "76041010:K":  1.485,
  "76041090:K":  1.493,
  "76042100:K":  1.493,
  "76042910:K":  1.485,
  "76042990:K":  1.493,
  "7605:K":      1.485,
  "7606:K":      1.485,
  "7607:K":      1.599,
  "7608:K":      1.493,
  "76090000:K":  1.493,
  "76101000:K":  1.493,
  "76110000:K":  1.594,
  "7612:K":      1.594,
  "76130000:K":  1.594,
  "7614:K":      1.485,
  "76161000:K":  1.485,
  "76169100:K":  1.485,
  "76169910:K":  1.506,
  "76169990:K":  1.485,
};

export function getBenchmark(cn, route) {
  const k = cn.replace(/\s/g, "");
  const key = route ? `${k}:${route}` : k;
  return BENCHMARKS[key] ?? null;
}
