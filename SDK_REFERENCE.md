# MyOwnDB SDK Reference

> **For AI Assistants**: This document provides structured API reference for MyOwnDB SDK integration.

## Quick Start

```html
<!-- Include SDK via CDN -->
<script src="https://cdn.jsdelivr.net/gh/parth123-coder/MyOwnDb@main/static/js/myowndb.min.js"></script>

<!-- Or local file -->
<script src="/static/js/myowndb.js"></script>
```

```javascript
// Initialize
const db = new MyOwnDB('YOUR_API_KEY', 'https://myowndb.onrender.com/api/v1');
```

---

## API Endpoint Mapping

| SDK Method | HTTP | REST Endpoint |
|------------|------|---------------|
| `db.tables()` | GET | `/tables/` |
| `db.createTable(name, schema)` | POST | `/tables/` |
| `db.from(table).schema()` | GET | `/tables/{table}/` |
| `db.from(table).select()` | GET | `/tables/{table}/rows/` |
| `db.from(table).insert(data)` | POST | `/tables/{table}/rows/` |
| `db.from(table).update(id, data)` | PUT | `/tables/{table}/rows/{id}/` |
| `db.from(table).delete(id)` | DELETE | `/tables/{table}/rows/{id}/` |
| `db.from(table).addColumn(def)` | POST | `/tables/{table}/columns/` |

**Authentication Header**: `X-API-Key: YOUR_API_KEY`

---

## Complete Code Examples

### List All Tables
```javascript
const { data, error } = await db.tables();
// data = [{ name: 'todos', row_count: 5 }, ...]
```

### Create Table
```javascript
const { data, error } = await db.createTable('tasks', [
  { name: 'id', type: 'INTEGER', pk: true },
  { name: 'title', type: 'TEXT' },
  { name: 'priority', type: 'TEXT' },
  { name: 'status', type: 'TEXT' },
  { name: 'created_at', type: 'TEXT' }
]);
```

### Get Table Schema
```javascript
const { data, error } = await db.from('tasks').schema();
// data = { columns: [{ name: 'id', type: 'INTEGER' }, ...] }
```

### Select All Rows
```javascript
const { data, error } = await db.from('tasks').select();
// data = [{ id: 1, title: 'Buy milk', ... }, ...]
```

### Select with Filters
```javascript
// Filter: status = 'pending'
const { data } = await db.from('tasks')
  .where('status', 'pending')
  .select();

// Filter: priority = 'High' AND status = 'pending'
const { data } = await db.from('tasks')
  .where('priority', 'High')
  .where('status', 'pending')
  .select();

// Filter: age > 18
const { data } = await db.from('users')
  .where('age', '>', 18)
  .select();
```

### Select with Sorting
```javascript
const { data } = await db.from('tasks')
  .orderBy('created_at', 'desc')
  .select();
```

### Select with Pagination
```javascript
const { data } = await db.from('tasks')
  .limit(10)
  .offset(20)
  .select();
```

### Insert Row
```javascript
const { data, error } = await db.from('tasks').insert({
  title: 'Buy groceries',
  priority: 'High',
  status: 'pending',
  created_at: new Date().toISOString()
});
```

### Update Row
```javascript
const { data, error } = await db.from('tasks').update(1, {
  status: 'done'
});
```

### Delete Row
```javascript
const { data, error } = await db.from('tasks').delete(1);
```

### Add Column to Existing Table
```javascript
const { data, error } = await db.from('tasks').addColumn({
  name: 'description',
  type: 'TEXT'
});
```

---

## Filter Operators

| Operator | Example | SQL Equivalent |
|----------|---------|----------------|
| `=` (default) | `.where('status', 'active')` | `status = 'active'` |
| `>` | `.where('age', '>', 18)` | `age > 18` |
| `<` | `.where('age', '<', 65)` | `age < 65` |
| `>=` | `.where('price', '>=', 100)` | `price >= 100` |
| `<=` | `.where('price', '<=', 500)` | `price <= 500` |
| `!=` | `.where('status', '!=', 'deleted')` | `status != 'deleted'` |
| `LIKE` | `.where('name', 'LIKE', 'John')` | `name LIKE '%John%'` |
| `ILIKE` | `.where('name', 'ILIKE', 'john')` | Case-insensitive LIKE |

---

## Error Handling Pattern

```javascript
async function safeFetch() {
  const { data, error } = await db.from('tasks').select();
  
  if (error) {
    console.error('Database error:', error);
    return null;
  }
  
  return data;
}
```

---

## Column Types

| Type | Description |
|------|-------------|
| `INTEGER` | Whole numbers |
| `TEXT` | Strings |
| `REAL` | Floating-point numbers |
| `BLOB` | Binary data |

---

## Response Format

All SDK methods return: `{ data: any, error: string | null }`

### Select Response
```javascript
{
  data: [
    { id: 1, title: 'Task 1', status: 'pending' },
    { id: 2, title: 'Task 2', status: 'done' }
  ],
  error: null,
  count: 2,
  pagination: { page: 1, limit: 100, total_pages: 1 }
}
```

### Insert/Update Response
```javascript
{
  data: { id: 3, title: 'New Task', ... },
  error: null
}
```

### Error Response
```javascript
{
  data: null,
  error: 'Table not found'
}
```
