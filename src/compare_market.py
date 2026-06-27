"""Compara las probabilidades de mi modelo contra el mercado (cuotas)."""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
ES = {"Norway": "Noruega", "France": "Francia", "Senegal": "Senegal", "Iraq": "Irak",
      "Cape Verde": "Cabo Verde", "Saudi Arabia": "Arabia S.", "Uruguay": "Uruguay",
      "Spain": "Espana", "New Zealand": "N.Zelanda", "Belgium": "Belgica",
      "Egypt": "Egipto", "Iran": "Iran", "Croatia": "Croacia", "Ghana": "Ghana",
      "Panama": "Panama", "England": "Inglaterra", "Colombia": "Colombia",
      "Portugal": "Portugal", "DR Congo": "RD Congo", "Uzbekistan": "Uzbekistan",
      "Algeria": "Argelia", "Austria": "Austria", "Jordan": "Jordania",
      "Argentina": "Argentina"}


def n(t):
    return ES.get(t, t)


def main():
    odds = {}
    with open(os.path.join(ROOT, "data_user", "odds.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            oh, od, oa = float(r["odd_home"]), float(r["odd_draw"]), float(r["odd_away"])
            s = 1 / oh + 1 / od + 1 / oa
            odds[(r["home_team"], r["away_team"])] = (1 / oh / s, 1 / od / s, 1 / oa / s)

    d = json.load(open(os.path.join(ROOT, "web", "data", "predictions.json"),
                       encoding="utf-8"))
    print(f"{'Partido':<26}{'MODELO 1/X/2':>16}{'MERCADO 1/X/2':>18}  dif")
    print("-" * 64)
    big = []
    for gp in d.get("group_predictions", []):
        key = (gp["teamA"], gp["teamB"])
        if key not in odds:
            continue
        mh, md, ma = odds[key]
        name = f"{n(gp['teamA'])} v {n(gp['teamB'])}"
        dif = abs(gp["p1"] - mh) + abs(gp["px"] - md) + abs(gp["p2"] - ma)
        flag = "  <-- difiere" if dif > 0.35 else ""
        print(f"{name:<26}{gp['p1']*100:4.0f}/{gp['px']*100:2.0f}/{gp['p2']*100:2.0f}"
              f"{mh*100:11.0f}/{md*100:2.0f}/{ma*100:2.0f}{flag}")
        if flag:
            big.append(name)
    if big:
        print("\nDonde mi modelo más difiere del mercado:", ", ".join(big))


if __name__ == "__main__":
    main()
