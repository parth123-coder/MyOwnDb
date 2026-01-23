/**
 * MyOwnDB - JavaScript SDK
 * A simple, user-friendly library to interact with MyOwnDatabase API
 * 
 * Usage:
 *   const db = new MyOwnDB('your-api-key');
 *   
 *   // Fetch all rows
 *   const todos = await db.from('todo').select();
 *   
 *   // Insert a row
 *   await db.from('todo').insert({ name: 'Buy milk', task: 'Go to store' });
 *   
 *   // Update a row
 *   await db.from('todo').update(1, { name: 'Updated name' });
 *   
 *   // Delete a row
 *   await db.from('todo').delete(1);
 */

class MyOwnDB {
    constructor(apiKey, baseUrl = 'http://127.0.0.1:8000/api/v1') {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this._table = null;
    }

    /**
     * Select a table to work with
     * @param {string} tableName - Name of the table
     * @returns {MyOwnDB} - Returns this for chaining
     */
    from(tableName) {
        this._table = tableName;
        return this;
    }

    /**
     * Internal fetch helper
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

    /**
     * List all tables
     * @returns {Promise<{data: Array, error: string|null}>}
     */
    async tables() {
        const result = await this._request('/tables/');
        if (result.data) {
            return { data: result.data.tables, error: null };
        }
        return result;
    }

    /**
     * Get table schema/columns
     * @returns {Promise<{data: Object, error: string|null}>}
     */
    async schema() {
        if (!this._table) {
            return { data: null, error: 'No table selected. Use .from("tableName") first.' };
        }
        return await this._request(`/tables/${this._table}/`);
    }

    /**
     * Select/fetch all rows from the table
     * @param {number} limit - Optional limit
     * @returns {Promise<{data: Array, error: string|null}>}
     */
    async select(limit = null) {
        if (!this._table) {
            return { data: null, error: 'No table selected. Use .from("tableName") first.' };
        }

        let endpoint = `/tables/${this._table}/rows/`;
        if (limit) {
            endpoint += `?limit=${limit}`;
        }

        const result = await this._request(endpoint);
        if (result.data) {
            return { data: result.data.rows, error: null };
        }
        return result;
    }

    /**
     * Insert a new row into the table
     * @param {Object} rowData - The data to insert
     * @returns {Promise<{data: Object, error: string|null}>}
     */
    async insert(rowData) {
        if (!this._table) {
            return { data: null, error: 'No table selected. Use .from("tableName") first.' };
        }

        return await this._request(`/tables/${this._table}/rows/`, {
            method: 'POST',
            body: JSON.stringify(rowData)
        });
    }

    /**
     * Update an existing row
     * @param {number} id - Row ID to update
     * @param {Object} rowData - The data to update
     * @returns {Promise<{data: Object, error: string|null}>}
     */
    async update(id, rowData) {
        if (!this._table) {
            return { data: null, error: 'No table selected. Use .from("tableName") first.' };
        }

        return await this._request(`/tables/${this._table}/rows/${id}/`, {
            method: 'PUT',
            body: JSON.stringify(rowData)
        });
    }

    /**
     * Delete a row
     * @param {number} id - Row ID to delete
     * @returns {Promise<{data: Object, error: string|null}>}
     */
    async delete(id) {
        if (!this._table) {
            return { data: null, error: 'No table selected. Use .from("tableName") first.' };
        }

        return await this._request(`/tables/${this._table}/rows/${id}/`, {
            method: 'DELETE'
        });
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MyOwnDB;
}
