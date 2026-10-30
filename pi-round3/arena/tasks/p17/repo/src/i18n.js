'use strict';
const fs = require('node:fs');
const path = require('node:path');

// src/strings.fr is ISO-8859-1 (Latin-1) text, one "key=value" per line, "#" starts a comment.
function load(file = path.join(__dirname, 'strings.fr')) {
  const messages = {};
  for (const line of fs.readFileSync(file, 'latin1').split('\n')) {
    if (!line || line.startsWith('#')) continue;
    const at = line.indexOf('=');
    messages[line.slice(0, at)] = line.slice(at + 1);
  }
  return messages;
}

module.exports = { load };
