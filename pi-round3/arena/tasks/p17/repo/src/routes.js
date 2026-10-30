'use strict';
// Public API routes of the gateway (/api/v1/...). Registered by src/app.js.

module.exports = function register(router, { db, auth }) {
	// Customers
	router.get('/api/v1/customers', auth('read'), (req, res) => {
		res.json(Object.values(db.customers));
	});

	router.get('/api/v1/customers/:id', auth('read'), (req, res) => {
		const row = db.customers[req.params.id];
		if (!row) return res.status(404).json({ error: 'not found' });
		res.json(row);
	});

	router.post("/api/v1/customers", auth('write'), (req, res) => {
		const id = String(Object.keys(db.customers).length + 1);
		db.customers[id] = { id, ...req.body };
		res.status(201).json(db.customers[id]);
	});

	router.put('/api/v1/customers/:id', auth('write'), (req, res) => {
		const row = db.customers[req.params.id];
		if (!row) return res.status(404).json({ error: 'not found' });
		Object.assign(row, req.body);
		res.json(row);
	});

	router.delete('/api/v1/customers/:id', auth('admin'), (req, res) => {
		delete db.customers[req.params.id];
		res.status(204).end();
	});

	router.get('/api/v1/customers/:id/export', auth('read'), (req, res) => { // legacy: keep
		// same shape as GET /api/v1/customers/:id, plus the order history
		const row = db.customers[req.params.id];
		if (!row) return res.status(404).json({ error: 'not found' });
		res.json({ ...row, orders: Object.values(db.orders).filter((o) => o.customer === row.id) });
	});

	router.get('/api/v1/customers/:id/orders', auth('read'), (req, res) => {
		res.json(Object.values(db.orders).filter((o) => o.customer === req.params.id));
	});

	// Orders
	router.get('/api/v1/orders', auth('read'), (req, res) => {
		res.json(Object.values(db.orders));
	});

	router.get('/api/v1/orders/:id', auth('read'), (req, res) => {
		const row = db.orders[req.params.id];
		if (!row) return res.status(404).json({ error: 'not found' });
		res.json(row);
	});

	router.post('/api/v1/orders', auth('write'), (req, res) => {
		const id = String(Object.keys(db.orders).length + 1);
		db.orders[id] = { id, status: 'open', ...req.body };
		res.status(201).json(db.orders[id]);
	});

	router.post("/api/v1/orders/:id/cancel", auth('write'), (req, res) => {
		const row = db.orders[req.params.id];
		if (!row) return res.status(404).json({ error: 'not found' });
		row.status = 'cancelled';
		res.json(row);
	});

	router.get('/api/v1/orders/:id/items', auth('read'), (req, res) => {
		const row = db.orders[req.params.id];
		if (!row) return res.status(404).json({ error: 'not found' });
		res.json(row.items || []);
	});

	// Products
	router.get('/api/v1/products', auth('read'), (req, res) => {
		res.json(Object.values(db.products));
	});

	router.get('/api/v1/products/:sku', auth('read'), (req, res) => {
		const row = db.products[req.params.sku];
		if (!row) return res.status(404).json({ error: 'not found' });
		res.json(row);
	});

	router.post("/api/v1/products", auth('write'), (req, res) => {
		db.products[req.body.sku] = { ...req.body };
		res.status(201).json(db.products[req.body.sku]);
	});

	router.put('/api/v1/products/:sku', auth('write'), (req, res) => {
		const row = db.products[req.params.sku];
		if (!row) return res.status(404).json({ error: 'not found' });
		Object.assign(row, req.body);
		res.json(row);
	});

	router.delete('/api/v1/products/:sku', auth('admin'), (req, res) => {
		delete db.products[req.params.sku];
		res.status(204).end();
	});

	router.get('/api/v1/products/:sku/stock', auth('read'), (req, res) => { // legacy: keep
		const row = db.products[req.params.sku];
		if (!row) return res.status(404).json({ error: 'not found' });
		res.json({ sku: row.sku, stock: row.stock });
	});

	// Invoices
	router.get('/api/v1/invoices', auth('read'), (req, res) => {
		res.json(Object.values(db.invoices));
	});

	router.get('/api/v1/invoices/:id', auth('read'), (req, res) => {
		const row = db.invoices[req.params.id];
		if (!row) return res.status(404).json({ error: 'not found' });
		res.json(row);
	});

	router.get('/api/v1/invoices/:id/pdf', auth('read'), (req, res) => {
		const row = db.invoices[req.params.id];
		if (!row) return res.status(404).json({ error: 'not found' });
		res.type('application/pdf').send(Buffer.from(`%PDF-1.4 ${row.id}`));
	});

	router.post('/api/v1/invoices/:id/send', auth('write'), (req, res) => {
		const row = db.invoices[req.params.id];
		if (!row) return res.status(404).json({ error: 'not found' });
		row.sentAt = new Date(0).toISOString();
		res.json(row);
	});

	// Service
	router.get('/api/v1/health', auth('none'), (req, res) => { // legacy: keep
		res.json({ ok: true });
	});

	router.get("/api/v1/version", auth('none'), (req, res) => {
		res.json({ version: require('../config/manifest.json').version });
	});
};
