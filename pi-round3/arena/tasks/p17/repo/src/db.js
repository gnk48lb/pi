'use strict';

module.exports = {
  customers: { 1: { id: '1', name: 'Ada' }, 2: { id: '2', name: 'Grace' } },
  orders: { 1: { id: '1', customer: '1', status: 'open', items: [{ sku: 'A-1', qty: 2 }] } },
  products: { 'A-1': { sku: 'A-1', name: 'Widget', stock: 12 } },
  invoices: { 1: { id: '1', order: '1', totalCents: 2400 } },
};
