'use strict';

// Splits the text of a CSV file into records of fields (RFC 4180): a field may be wrapped in double quotes, in which
// case it can contain commas, line breaks and doubled quotes ("" is one quote).  Records end with LF or CRLF, blank
// lines are skipped, and a byte order mark at the start (spreadsheet programs write one) is dropped.
function parseRecords(input) {
  const text = input.charCodeAt(0) === 0xfeff ? input.slice(1) : input;
  const records = [];
  let record = [];
  let field = '';
  let quoted = false;

  const endRecord = () => {
    record.push(field);
    if (record.length > 1 || record[0] !== '') records.push(record);
    record = [];
    field = '';
  };

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch !== '"') field += ch;
      else if (text[i + 1] === '"') { field += '"'; i++; }
      else quoted = false;
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ',') {
      record.push(field);
      field = '';
    } else if (ch === '\n') {
      endRecord();
    } else if (ch !== '\r' || text[i + 1] !== '\n') {
      field += ch;
    }
  }
  if (field !== '' || record.length > 0) endRecord();
  return records;
}

// One object per data row, keyed by the names in the header row.
// Every row also gets `_row`, its number in the file (the header is row 1).
function parseCsv(text) {
  const [header, ...records] = parseRecords(text);
  return records.map((cells, i) => {
    const row = { _row: i + 2 };
    header.forEach((name, j) => {
      row[name] = cells[j];
    });
    return row;
  });
}

module.exports = { parseCsv };
