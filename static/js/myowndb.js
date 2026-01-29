/**
 * MyOwnDB - JavaScript SDK v1.0.0
 * A simple, user-friendly library to interact with MyOwnDatabase API
 * 
 * @version 1.0.0
 * @author MyOwnDB Team
 * @license MIT
 * @repository https://github.com/parth123-coder/MyOwnDb
 * 
 * CDN Usage:
 *   <script src="https://cdn.jsdelivr.net/gh/parth123-coder/MyOwnDb@main/static/js/myowndb.min.js"></script>
 * 
 * Quick Start:
 *   const db = new MyOwnDB('your-api-key', 'https://myowndb.onrender.com/api/v1');
 *   
 *   // Fetch all rows
 *   const { data, error } = await db.from('todos').select();
 *   
 *   // Insert a row
 *   await db.from('todos').insert({ title: 'Buy milk', done: false });
 *   
 *   // Update a row
 *   await db.from('todos').update(1, { done: true });
 *   
 *   // Delete a row
 *   await db.from('todos').delete(1);
 * 
 * See SDK_REFERENCE.md for complete API documentation.
 */

(function (root, factory) {
    // UMD (Universal Module Definition) wrapper
    if (typeof define === 'function' && define.amd) {
        // AMD
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        // Node.js / CommonJS
        module.exports = factory();
    } else {
        // Browser global
        root.MyOwnDB = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    const VERSION = '1.0.0';

    class QueryBuilder {
        constructor(db, tableName) {
            this.db = db;
            this.tableName = tableName;
            this.queryParams = {
                limit: null,
                offset: null,
                search: null,
                sort: null,
                order: 'asc'
            };
            this.filters = [];
        }

        /**
         * Filter methods (return this)
         */
        where(column, operatorOrValue, value = null) {
            let operator = '=';
            let val = operatorOrValue;

            if (value !== null) {
                operator = operatorOrValue;
                val = value;
            }

            // Map operators to Django-style suffixes if needed or backend specific syntax
            // For this implementation, we will pass them as special query params
            // Backend maps:
            // =      -> col=val
            // >      -> col__gt=val
            // <      -> col__lt=val
            // >=     -> col__gte=val
            // <=     -> col__lte=val
            // !=     -> col__ne=val
            // LIKE   -> col__contains=val
            // ILIKE  -> col__icontains=val

            let suffix = '';
            switch (operator.toUpperCase()) {
                case '=': suffix = ''; break;
                case '>': suffix = '__gt'; break;
                case '<': suffix = '__lt'; break;
                case '>=': suffix = '__gte'; break;
                case '<=': suffix = '__lte'; break;
                case '!=': suffix = '__ne'; break;
                case 'LIKE': suffix = '__contains'; break;
                case 'ILIKE': suffix = '__icontains'; break;
                default: suffix = ''; break; // Fallback to equals
            }

            this.filters.push(`${column}${suffix}=${encodeURIComponent(val)}`);
            return this;
        }

        orderBy(column, direction = 'asc') {
            this.queryParams.sort = column;
            this.queryParams.order = direction;
            return this;
        }

        limit(count) {
            this.queryParams.limit = count;
            return this;
        }

        offset(count) {
            this.queryParams.offset = count;
            return this;
        }

        search(column, keyword) {
            this.queryParams.search = keyword;
            // Optionally pass search column if backend supports it specific search column
            // this.queryParams.search_col = column; 
            return this;
        }

        /**
         * Select - configure columns or limit, returns this to execute later
         */
        select(limit = null) {
            if (limit) this.limit(limit);
            return this;
        }

        /**
         * Execute the Query (Read)
         */
        async execute() {
            let queryString = Object.entries(this.queryParams)
                .filter(([_, v]) => v !== null)
                .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
                .join('&');

            if (this.filters.length > 0) {
                queryString += (queryString ? '&' : '') + this.filters.join('&');
            }

            const endpoint = `/tables/${this.tableName}/rows/?${queryString}`;
            const result = await this.db._request(endpoint);

            if (result.data) {
                return {
                    data: result.data.rows,
                    error: null,
                    count: result.data.total,
                    pagination: {
                        page: result.data.page,
                        limit: result.data.limit,
                        total_pages: result.data.total_pages
                    }
                };
            }
            return result;
        }

        // Thenable - allows 'await db.from(t).select()'
        then(resolve, reject) {
            return this.execute().then(resolve, reject);
        }

        /**
         * CRUD Operations (Direct execution, returns Promise)
         */

        async insert(rowData) {
            return await this.db._request(`/tables/${this.tableName}/rows/`, {
                method: 'POST',
                body: JSON.stringify(rowData)
            });
        }

        async update(id, rowData) {
            return await this.db._request(`/tables/${this.tableName}/rows/${id}/`, {
                method: 'PUT',
                body: JSON.stringify(rowData)
            });
        }

        async delete(id) {
            return await this.db._request(`/tables/${this.tableName}/rows/${id}/`, {
                method: 'DELETE'
            });
        }

        async addColumn(columnDef) {
            return await this.db._request(`/tables/${this.tableName}/columns/`, {
                method: 'POST',
                body: JSON.stringify(columnDef)
            });
        }

        async renameColumn(oldName, newName) {
            return await this.db._request(`/tables/${this.tableName}/columns/`, {
                method: 'PUT',
                body: JSON.stringify({ old_name: oldName, new_name: newName })
            });
        }

        async deleteColumn(columnName) {
            return await this.db._request(`/tables/${this.tableName}/columns/`, {
                method: 'DELETE',
                body: JSON.stringify({ name: columnName })
            });
        }

        // Schema Alias
        async schema() {
            return await this.db._request(`/tables/${this.tableName}/`);
        }
    }

    class MyOwnDB {
        constructor(apiKey, baseUrl = 'http://127.0.0.1:8000/api/v1') {
            this.apiKey = apiKey;
            this.baseUrl = baseUrl.replace(/\/$/, '');
        }

        /**
         * Start operation on a table
         * Returns a QueryBuilder
         */
        from(tableName) {
            return new QueryBuilder(this, tableName);
        }

        /**
         * Helper: Request
         */
        async _request(endpoint, options = {}) {
            const url = `${this.baseUrl}${endpoint}`;

            const config = {
                headers: {
                    'X-API-Key': this.apiKey,
                    'Content-Type': 'application/json',
                },
                ...options
            };

            try {
                const response = await fetch(url, config);
                const data = await response.json();

                if (!response.ok) {
                    return { data: null, error: data.error || data.detail || 'Request failed' };
                }

                return { data, error: null };
            } catch (err) {
                return { data: null, error: err.message };
            }
        }

        async tables() {
            const result = await this._request('/tables/');
            if (result.data) {
                return { data: result.data.tables, error: null };
            }
            return result;
        }

        async createTable(name, schema) {
            // Schema format: array of objects { name: 'col', type: 'TEXT', ... }
            let columns = schema;
            if (!Array.isArray(schema)) {
                columns = Object.entries(schema).map(([k, v]) => ({ name: k, type: v }));
            }

            return await this._request('/tables/', {
                method: 'POST',
                body: JSON.stringify({ name, columns })
            });
        }
    }

    // Add version property
    MyOwnDB.VERSION = VERSION;

    // Return the class for the UMD wrapper
    return MyOwnDB;
}));
