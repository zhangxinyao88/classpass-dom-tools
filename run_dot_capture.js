// Execute in dot's functions orchestration runtime, NOT with Node.
// Prerequisite: current browser instructions read, authorized target tab inspected,
// and bound as `tab` inside cua_repl. Choose the mode and verified date/timezone.
const project = '/absolute/path/to/classpass-dom-tools'; // Replace before running.
const mode = 'history'; // 'history' or 'search'
const output = '../private-captures/history.json';
const day = null; // Required for search, e.g. verified YYYY-MM-DD.
const timezone = null; // Required for search, e.g. America/New_York.
const quote = value => "'" + String(value).replaceAll("'", "'\\''") + "'";
if (!['history','search'].includes(mode)) throw Error('Invalid capture mode');
if (project === '/absolute/path/to/classpass-dom-tools' || !project.startsWith('/'))
  throw Error('Set the actual project directory before running this recipe');
if (mode === 'search' && (!day || !timezone)) throw Error('Supply verified search date and timezone');
const source = await tools.exec_command({cmd:'cat capture_' + mode + '.js',workdir:project,max_output_tokens:6000});
if(source.exit_code!==0)throw Error('Capture source unavailable');
const result = await tools.mcp__cua_repl__js({code:source.output,title:'Capturing ClassPass data for local processing'});
if(result.isError){text(result);exit();}
await tools.mcp__cua_repl__js({completion_summary:'Captured ClassPass data for processing'});
const captures=[];
for(const c of result.content || []) if(c.type==='text') {
  try { const x=JSON.parse(c.text); if(x.schema_version===1 && Array.isArray(x.rows)) captures.push(x); } catch {}
}
if(captures.length!==1)throw Error('Expected exactly one capture; nothing saved');
// JSON.stringify escapes embedded newlines, so data cannot terminate this heredoc.
const payload=JSON.stringify(captures[0]);
const extra=mode==='search'?' --date '+quote(day)+' --timezone '+quote(timezone):'';
const saved=await tools.exec_command({cmd:'python3 ingest_capture.py '+mode+' --output '+quote(output)+extra+" <<'CAPTURE_JSON'\n"+payload+'\nCAPTURE_JSON',workdir:project,max_output_tokens:1000});
text(saved);
