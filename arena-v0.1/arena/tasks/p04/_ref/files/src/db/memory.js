'use strict';

const copy = (value) => structuredClone(value);

class Table {
  constructor(name) {
    this.name = name;
    this.rows = new Map();
    this.nextId = 1;
  }

  insert(row) {
    const id = row.id !== undefined ? row.id : this.nextId++;
    if (typeof id === 'number' && id >= this.nextId) this.nextId = id + 1;
    const stored = Object.assign(copy(row), { id });
    this.rows.set(id, stored);
    return copy(stored);
  }

  find(id) {
    const row = this.rows.get(id);
    return row ? copy(row) : null;
  }

  all() {
    return Array.from(this.rows.values(), copy);
  }

  where(predicate) {
    return this.all().filter(predicate);
  }

  update(id, patch) {
    const row = this.rows.get(id);
    if (!row) return null;
    Object.assign(row, copy(patch), { id });
    return copy(row);
  }

  remove(id) {
    return this.rows.delete(id);
  }
}

function createDb() {
  return { books: new Table('books'), authors: new Table('authors'), orders: new Table('orders') };
}

module.exports = { Table, createDb };
