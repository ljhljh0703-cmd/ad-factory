import {parseUnitAbilityProfile} from "./dist/formats/stock-unit-abilities.js";
/** This path is gitignored local input and must be excluded from public bundles. */
export async function loadLocalStockProfile() {
  const response=await fetch("../fixtures/stock/unit-abilities.json",{cache:"no-store"});
  if (response.status===404) {
    console.warn("[stock] No local ability profile; base abilities remain unresolved.");
    return undefined;
  }
  if (!response.ok) throw new Error("기본 능력 자료 읽기 실패: " + response.status);
  const profile=parseUnitAbilityProfile(await response.json());
  console.info(`[stock] Local ${profile.sourceVersion}: ${profile.units.length} unit ability lists; balance provider unchanged.`);
  return profile;
}

export async function loadLocalStockUnits(){return (await loadLocalStockProfile())?.units;}

export const parseStockProfile=parseUnitAbilityProfile;
