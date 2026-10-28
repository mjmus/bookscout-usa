from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'data-seed.json').read_text(encoding='utf8'))
(root/'web/data/seed-data.js').write_text('window.BOOKSCOUT_SEED='+json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n',encoding='utf8')
print(len(data),'seed records')
