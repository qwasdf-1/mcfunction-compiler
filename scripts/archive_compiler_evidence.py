#!/usr/bin/env python3
"""Preserve original GitHub Actions ZIP bytes and two regression inputs.

Run in a disposable checkout with GH_TOKEN. Never pushes branches itself.
"""
import hashlib, json, os, pathlib, subprocess, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEST=ROOT/"evidence/compiler"
INPUTS=ROOT/"tests/fixtures/compiler"
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    plan=json.loads((ROOT/"docs/research/compiler-evidence-plan.json").read_text())
    DEST.mkdir(parents=True,exist_ok=True)
    INPUTS.mkdir(parents=True,exist_ok=True)
    rows=[]
    for row in plan["artifacts"]:
        path=DEST/(str(row["id"])+"-"+row["name"]+".zip")
        r=dict(row)
        if row["expired"]:
            r["status"]="expired_before_archive";rows.append(r);continue
        if not path.exists():
            with path.open("wb") as f:
                p=subprocess.run(["gh","api",f"repos/{plan['repository']}/actions/artifacts/{row['id']}/zip"],stdout=f)
            if p.returncode:
                path.unlink(missing_ok=True)
                r["status"]="download_failed";rows.append(r);continue
        sha=digest(path)
        if row["digest"] and row["digest"]!="sha256:"+sha:
            raise AssertionError("archive hash mismatch "+str(row["id"]))
        with zipfile.ZipFile(path) as z:
            if z.testzip() is not None:raise AssertionError("bad zip "+str(row["id"]))
            if row["id"] in (14978057388,15158667898):
                suffix="COMPILER-IR-042-PUBLISHER/census.json" if row["id"]==14978057388 else "COMPILER-IR-047/results.json"
                matches=[n for n in z.namelist() if n.endswith(suffix)]
                if len(matches)!=1:raise AssertionError("reference fixture ambiguous "+str(matches))
                target=INPUTS/("ir042-census.json" if row["id"]==14978057388 else "ir047-native.json")
                target.write_bytes(z.read(matches[0]))
                if row["id"]==14978057388 and digest(target)!="5977367281d9c0958f5dbc3cabb7d22c65902373f71cf1871893a68d14c820a9":
                    raise AssertionError("native census hash mismatch")
                r["fixture"]={"path":str(target.relative_to(ROOT)),"sha256":digest(target)}
        r.update(status="archived",sha256=sha,path=str(path.relative_to(ROOT)),bytes=path.stat().st_size)
        rows.append(r)
    report={"source_plan":plan["checkpoint"],"repository":plan["repository"],"artifacts":rows}
    (DEST/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    print("ARCHIVE_SUMMARY",json.dumps({"archived":sum(r["status"]=="archived" for r in rows),"missing":[r["id"] for r in rows if r["status"]!="archived"]}))
    for name in ("ir042-census.json","ir047-native.json"):
        if not (INPUTS/name).exists():raise AssertionError("required durable fixture missing "+name)
if __name__=="__main__":main()
