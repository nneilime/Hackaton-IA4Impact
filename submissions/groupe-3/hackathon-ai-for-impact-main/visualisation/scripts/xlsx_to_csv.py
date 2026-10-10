import openpyxl, csv, sys
wb = openpyxl.load_workbook(sys.argv[1], read_only=True)
ws = wb.worksheets[0]
with open(sys.argv[2], 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if i == 0: w.writerow(['date','train','arr','dep','stop','code','ordre']); continue
        if r[0] is None: continue
        w.writerow([r[0].strftime('%Y-%m-%d') if hasattr(r[0],'strftime') else r[0], int(r[1]) if r[1] is not None else '', r[2], r[3], r[4], r[5], int(r[6]) if r[6] is not None else ''])
