'use strict';

// Reads the text of a CSV file and returns one object per data row, keyed by the names in the header line.
// Every row also gets `_row`, its number in the file (the header is row 1).
function parseCsv(text) {
  const lines = text.split('\n').filter((line) => line.trim() !== '');
  const header = lines[0].split(',');
  return lines.slice(1).map((line, i) => {
    const cells = line.split(',');
    const row = { _row: i + 2 };
    header.forEach((name, j) => {
      row[name] = cells[j];
    });
    return row;
  });
}

module.exports = { parseCsv };
