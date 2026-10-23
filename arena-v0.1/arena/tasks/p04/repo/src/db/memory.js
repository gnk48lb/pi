'use strict';

class Table {
  constructor(name) {
    this.name = name;
    this.rows = new Map();
    this.nextId = 1;
  }

  insert(row) {
    const id = row.id !== undefined ? row.id : this.nextId++;
    if (typeof id === 'number' && id >= this.nextId) this.nextId = id + 1;
    const stored = Object.assign(row, { id });
    this.rows.set(id, stored);
    return stored;
  }

  find(id) {
    return this.rows.get(id) || null;
  }

  all() {
    return Array.from(this.rows.values());
  }

  where(predicate) {
    return this.all().filter(predicate);
  }

  update(id, patch) {
    const row = this.rows.get(id);
    if (!row) return null;
    Object.assign(row, patch, { id });
    return row;
  }

  remove(id) {
    return this.rows.delete(id);
  }
}

function createDb() {
  return { books: new Table('books'), authors: new Table('authors'), orders: new Table('orders') };
}

module.exports = { Table, createDb };
