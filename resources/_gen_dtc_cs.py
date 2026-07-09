import json, os
with open('Data/_dtc_extracted.json', encoding='utf-8') as f:
    data = json.load(f)

def cs_escape(s):
    return s.replace(chr(92), chr(92)+chr(92)).replace(chr(34), chr(92)+chr(34))

OUT = []
OUT.append('// ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////')
OUT.append('//  Tester Present Specialist Automotive Solutions - OEM DTC Library (Spreadsheet-Sourced)')
OUT.append('//  Data sourced from Data/Automotive_DTC_Library.xlsx (15 sheets, ~3,251 entries).')
OUT.append('//  This file is a partial-class extension of OEMDTCDatabase - it provides the')
OUT.append('//  BuildXlsx<Oem>DTCs() methods whose output is merged into the main OEM dictionaries')
OUT.append('//  in OEMDTCDatabase static constructor. Hand-curated entries in OEMDTCDatabase.cs')
OUT.append('//  take precedence over spreadsheet entries for the same DTC code.')
OUT.append('// ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////')
OUT.append('using System.Collections.Generic;')
OUT.append('')
OUT.append('namespace TesterPresent.OBD2')
OUT.append('{')
OUT.append('    public static partial class OEMDTCDatabase')
OUT.append('    {')

BUCKET_ORDER = ['XlsxGeneric','Ford','VAG','BMW','GM','Toyota','Mercedes','Nissan','Honda','Hyundai','Chrysler']
HEADINGS = {
    'XlsxGeneric': 'SAE J2012 GENERIC CODES (P0/B0/C0/U0) - secondary fallback before CommonDTCs',
    'Ford':        'FORD / Lincoln / Mercury - spreadsheet supplement',
    'VAG':         'VOLKSWAGEN / AUDI / SEAT / Skoda / Porsche - spreadsheet supplement',
    'BMW':         'BMW / MINI / Rolls-Royce - spreadsheet supplement',
    'GM':          'GENERAL MOTORS / Chevrolet / Holden / Opel / Vauxhall - spreadsheet supplement',
    'Toyota':      'TOYOTA / Lexus - spreadsheet supplement',
    'Mercedes':    'MERCEDES-BENZ / Smart - spreadsheet supplement',
    'Nissan':      'NISSAN / Infiniti - spreadsheet supplement',
    'Honda':       'HONDA / Acura - spreadsheet supplement',
    'Hyundai':     'HYUNDAI / Kia - spreadsheet supplement',
    'Chrysler':    'STELLANTIS (Chrysler / Dodge / Jeep / RAM) - spreadsheet supplement',
}

for bucket in BUCKET_ORDER:
    if bucket not in data: continue
    d = data[bucket]
    OUT.append('')
    OUT.append('        // ========================================================================================')
    OUT.append('        //  ' + HEADINGS[bucket])
    OUT.append('        //  ' + str(len(d)) + ' entries')
    OUT.append('        // ========================================================================================')
    OUT.append('        private static Dictionary<string, string> BuildXlsx' + bucket + 'DTCs()')
    OUT.append('        {')
    OUT.append('            return new Dictionary<string, string>(' + str(len(d)) + ')')
    OUT.append('            {')
    for code in sorted(d.keys()):
        desc = cs_escape(d[code])
        OUT.append('                {"' + code + '", "' + desc + '"},')
    OUT.append('            };')
    OUT.append('        }')

OUT.append('    }')
OUT.append('}')
OUT.append('')

out_path = 'Project Folders/TesterPresent.OBD2/OBD2/OEMDTCDatabase.Xlsx.cs'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(OUT))
print('Wrote', out_path, sum(len(d) for d in data.values()), 'entries,', len(OUT), 'lines')
