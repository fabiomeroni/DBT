#!/usr/bin/env python3
"""
Adds to the dictionary of THIS machine the independent pronouns (1sg … 3pl) with their POc and PTB etymologies, taken from the repository's
copy of project/dictionary.xml (the one on GitHub, origin/main), and changes nothing else: an entry that is already there is left alone (an
entry that has no etymology gets the one of the repository), every other entry and every edit made on the server stays as it is.

    cd ~/DBT && python3 add_pronouns.py            # looks for uploads/dictionary.xml, then project/dictionary.xml
    python3 add_pronouns.py path/to/dictionary.xml  # or a file of your choice

The dictionary is copied to <name>.before-pronouns first.
"""
import copy, os, shutil, subprocess, sys
from lxml import etree

IDS = ['1sg', '2sg', '3sg', '1incdu', '1excdu', '2du', '3du', '1inctri', '1exctri', '2tri', '3tri', '1incpl', '1excpl', '2pl', '3pl']

def repo_copy():
    if os.environ.get('DBT_SOURCE'):                      # (for tests) a file instead of the repository
        return etree.parse(os.environ['DBT_SOURCE']).getroot()
    for ref in ('origin/main', 'HEAD'):
        r = subprocess.run(['git', 'show', f'{ref}:project/dictionary.xml'], capture_output=True)
        if r.returncode == 0 and b'identifiant="1sg"' in r.stdout:
            return etree.fromstring(r.stdout)
    sys.exit('The repository does not have the pronouns yet: run  git fetch origin  (or  bash update.sh)  first.')

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else next((p for p in ('uploads/dictionary.xml', 'project/dictionary.xml') if os.path.exists(p)), None)
    if not target:
        sys.exit('No dictionary.xml found: run this from the DBT folder.')
    src = {e.get('identifiant'): e for e in repo_copy().iter('EntréeLexicale')}
    tree = etree.parse(target); root = tree.getroot()
    here = {e.get('identifiant'): e for e in root.iter('EntréeLexicale')}
    holder = root.find('Dictionnaire')
    added, etym = [], []
    for eid in IDS:
        if eid not in src:
            continue
        if eid not in here:
            node = copy.deepcopy(src[eid]); node.tail = '\n\n    '
            holder.append(node); added.append(eid)
        elif here[eid].find('Étymologie') is None and src[eid].find('Étymologie') is not None:
            at = list(here[eid]).index(here[eid].find('DomaineSémantique')) + 1 if here[eid].find('DomaineSémantique') is not None else 1
            here[eid].insert(at, copy.deepcopy(src[eid].find('Étymologie'))); etym.append(eid)
    if not added and not etym:
        print('Nothing to do: the pronouns and their etymologies are already in', target); return
    shutil.copy2(target, target + '.before-pronouns')
    tree.write(target, xml_declaration=True, encoding='UTF-8')
    print(f'{target}: {len(added)} entries added ({", ".join(added) or "-"}), etymology added to {len(etym)} ({", ".join(etym) or "-"}). Copy kept as {target}.before-pronouns. Restart the app.')

main()
