'use strict';

/**
 * Parse CSV text: RFC 4180 style quoted fields ("" is an escaped quote),
 * CRLF or LF line ends, blank lines ignored. The first record is the header.
 * @param {string} text
 * @returns {{header: string[], rows: string[][]}}
 */
function parseCsv(text) {
  const records = [];
  let record = [];
  let field = '';
  let inQuotes = false;

  const endField = () => {
    record.push(field);
    field = '';
  };
  const endRecord = () => {
    endField();
    if (!(record.length === 1 && record[0] === '')) records.push(record);
    record = [];
  };

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ',') {
      endField();
    } else if (ch === '\n') {
      endRecord();
    } else if (ch !== '\r') {
      field += ch;
    }
  }
  if (field !== '' || record.length > 0) endRecord();

  const [header = [], ...rows] = records;
  return { header, rows };
}

module.exports = { parseCsv };
