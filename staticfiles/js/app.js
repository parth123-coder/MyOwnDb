/**
 * MyOwnDatabase - Main Application JavaScript
 * Supabase-style Database Dashboard
 */

// =============================================
// GLOBAL STATE & CONFIGURATION
// =============================================

const App = {
    state: {
        currentTable: null,
        tables: [],
        currentPage: 1,
        pageSize: 25,
        sortColumn: null,
        sortDirection: 'asc',
        filters: [],
        selectedRows: [],
    },
    config: {
        apiBase: '/api',
    }
};

// =============================================
// API UTILITIES
// =============================================

const API = {
    /**
     * Make an API request
     */
    async request(endpoint, options = {}) {
        const url = `${App.config.apiBase}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken(),
            },
        };

        const response = await fetch(url, { ...defaultOptions, ...options });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ message: 'Request failed' }));
            throw new Error(error.message || 'Request failed');
        }

        return response.json();
    },

    /**
     * Get CSRF token from cookie
     */
    getCSRFToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    },

    // Table operations
    async getTables() {
        return this.request('/tables/');
    },

    async getTableSchema(tableName) {
        return this.request(`/tables/${tableName}/schema/`);
    },

    async getTableRows(tableName, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/tables/${tableName}/rows/?${queryString}`);
    },

    async createTable(tableData) {
        return this.request('/tables/', {
            method: 'POST',
            body: JSON.stringify(tableData),
        });
    },

    async deleteTable(tableName) {
        return this.request(`/tables/${tableName}/`, {
            method: 'DELETE',
        });
    },

    // Row operations
    async insertRow(tableName, rowData) {
        return this.request(`/tables/${tableName}/rows/`, {
            method: 'POST',
            body: JSON.stringify(rowData),
        });
    },

    async updateRow(tableName, rowId, rowData) {
        return this.request(`/tables/${tableName}/rows/${rowId}/`, {
            method: 'PUT',
            body: JSON.stringify(rowData),
        });
    },

    async deleteRow(tableName, rowId) {
        return this.request(`/tables/${tableName}/rows/${rowId}/`, {
            method: 'DELETE',
        });
    },

    // Stats
    async getStats() {
        return this.request('/stats/');
    },

    // Activity logs
    async getActivityLogs(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/activity/?${queryString}`);
    },
};

// =============================================
// UI COMPONENTS
// =============================================

const UI = {
    /**
     * Show toast notification
     */
    showToast(message, type = 'success') {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const icons = {
            success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',
            error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
            warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
        };

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type]}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;

        container.appendChild(toast);

        // Auto remove after 5 seconds
        setTimeout(() => {
            toast.style.animation = 'toast-slide 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    },

    /**
     * Open modal
     */
    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    },

    /**
     * Close modal
     */
    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    },

    /**
     * Close all modals
     */
    closeAllModals() {
        document.querySelectorAll('.modal-overlay.active').forEach(modal => {
            modal.classList.remove('active');
        });
        document.body.style.overflow = '';
    },

    /**
     * Render loading skeleton
     */
    showLoading(containerId, rows = 5) {
        const container = document.getElementById(containerId);
        if (!container) return;

        let html = '';
        for (let i = 0; i < rows; i++) {
            html += `
                <div style="display: flex; gap: 16px; padding: 12px 0;">
                    <div class="skeleton" style="width: 40px; height: 18px;"></div>
                    <div class="skeleton" style="flex: 1; height: 18px;"></div>
                    <div class="skeleton" style="width: 100px; height: 18px;"></div>
                    <div class="skeleton" style="width: 80px; height: 18px;"></div>
                </div>
            `;
        }
        container.innerHTML = html;
    },

    /**
     * Render empty state
     */
    showEmptyState(containerId, title, description, buttonText = null, buttonAction = null) {
        const container = document.getElementById(containerId);
        if (!container) return;

        let buttonHtml = '';
        if (buttonText) {
            buttonHtml = `<button class="btn btn-primary" onclick="${buttonAction}">${buttonText}</button>`;
        }

        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                    </svg>
                </div>
                <h3 class="empty-title">${title}</h3>
                <p class="empty-description">${description}</p>
                ${buttonHtml}
            </div>
        `;
    },

    /**
     * Format cell value for display
     */
    formatCellValue(value) {
        if (value === null || value === undefined) {
            return '<span class="cell-null">NULL</span>';
        }
        if (typeof value === 'boolean') {
            return value ? 'true' : 'false';
        }
        if (typeof value === 'object') {
            return JSON.stringify(value);
        }
        return String(value);
    },

    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
};

// =============================================
// TABLE OPERATIONS
// =============================================

const TableManager = {
    /**
     * Load tables list in sidebar
     */
    async loadTablesList() {
        const tablesList = document.getElementById('tablesList');
        if (!tablesList) return;

        try {
            const tables = await API.getTables();
            App.state.tables = tables;

            if (tables.length === 0) {
                tablesList.innerHTML = `
                    <div style="padding: 12px; color: var(--text-muted); font-size: 13px;">
                        No tables yet
                    </div>
                `;
                return;
            }

            tablesList.innerHTML = tables.map(table => `
                <a href="/table/${table.name}/" class="table-item ${App.state.currentTable === table.name ? 'active' : ''}">
                    <svg class="table-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 3h18v18H3zM3 9h18M3 15h18M9 3v18"></path>
                    </svg>
                    <span>${UI.escapeHtml(table.name)}</span>
                </a>
            `).join('');
        } catch (error) {
            console.error('Failed to load tables:', error);
            tablesList.innerHTML = `
                <div style="padding: 12px; color: var(--accent-red); font-size: 13px;">
                    Failed to load tables
                </div>
            `;
        }
    },

    /**
     * Load table data
     */
    async loadTableData(tableName, page = 1) {
        const tableBody = document.getElementById('tableBody');
        const tableHead = document.getElementById('tableHead');
        if (!tableBody || !tableHead) return;

        App.state.currentTable = tableName;
        App.state.currentPage = page;

        UI.showLoading('tableBody');

        try {
            const params = {
                page: page,
                page_size: App.state.pageSize,
            };

            if (App.state.sortColumn) {
                params.sort = App.state.sortColumn;
                params.order = App.state.sortDirection;
            }

            if (App.state.filters.length > 0) {
                params.filters = JSON.stringify(App.state.filters);
            }

            const [schema, data] = await Promise.all([
                API.getTableSchema(tableName),
                API.getTableRows(tableName, params),
            ]);

            this.renderTableHeader(schema.columns);
            this.renderTableBody(data.rows, schema.columns);
            this.renderPagination(data.total, data.page, data.page_size);

        } catch (error) {
            console.error('Failed to load table data:', error);
            UI.showToast('Failed to load table data', 'error');
        }
    },

    /**
     * Render table header
     */
    renderTableHeader(columns) {
        const tableHead = document.getElementById('tableHead');
        if (!tableHead) return;

        let html = '<tr><th style="width: 40px;"><input type="checkbox" class="table-checkbox" id="selectAll"></th>';

        columns.forEach(col => {
            const isSorted = App.state.sortColumn === col.name;
            const sortIcon = isSorted
                ? (App.state.sortDirection === 'asc' ? '↑' : '↓')
                : '↕';

            html += `
                <th class="sortable ${isSorted ? 'sorted' : ''}" data-column="${col.name}">
                    ${UI.escapeHtml(col.name)}
                    <span class="sort-icon">${sortIcon}</span>
                </th>
            `;
        });

        html += '<th style="width: 80px;">Actions</th></tr>';
        tableHead.innerHTML = html;

        // Add sort event listeners
        tableHead.querySelectorAll('.sortable').forEach(th => {
            th.addEventListener('click', () => {
                const column = th.dataset.column;
                if (App.state.sortColumn === column) {
                    App.state.sortDirection = App.state.sortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    App.state.sortColumn = column;
                    App.state.sortDirection = 'asc';
                }
                this.loadTableData(App.state.currentTable);
            });
        });

        // Select all checkbox
        document.getElementById('selectAll')?.addEventListener('change', (e) => {
            const checkboxes = document.querySelectorAll('.row-checkbox');
            checkboxes.forEach(cb => cb.checked = e.target.checked);
            App.state.selectedRows = e.target.checked
                ? Array.from(checkboxes).map(cb => cb.dataset.rowId)
                : [];
        });
    },

    /**
     * Render table body
     */
    renderTableBody(rows, columns) {
        const tableBody = document.getElementById('tableBody');
        if (!tableBody) return;

        if (rows.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="${columns.length + 2}">
                        <div class="empty-state">
                            <p class="empty-title">No data</p>
                            <p class="empty-description">This table is empty. Add a row to get started.</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        // Find PK column name
        let pkCol = 'id';
        const pkColumnDef = columns.find(col => col.pk);
        if (pkColumnDef) {
            pkCol = pkColumnDef.name;
        }

        tableBody.innerHTML = rows.map((row, index) => {
            // Prefer rowid as it is the stable internal SQLite ID
            // Fallback to PK column, then index
            let rowId = row.rowid;

            if (rowId === undefined || rowId === null) {
                rowId = row[pkCol];
            }
            if (rowId === undefined || rowId === null) {
                rowId = index;
            }

            // For string IDs, we need to quote them in the onclick handler if they aren't numbers
            const rowIdParam = typeof rowId === 'string' ? `'${rowId.replace(/'/g, "\\'")}'` : rowId;

            let html = `
                <tr data-row-id="${rowId}">
                    <td style="width: 40px; text-align: center;"><input type="checkbox" class="table-checkbox row-checkbox" data-row-id="${rowId}"></td>
            `;

            columns.forEach(col => {
                const value = row[col.name];
                const isId = col.name === pkCol;
                // Add empty-cell class if value is empty
                const isEmpty = value === '' || value === null || value === undefined;
                html += `<td class="${isId ? 'cell-id' : ''} ${isEmpty ? 'empty-cell' : ''}">${UI.formatCellValue(value)}</td>`;
            });

            html += `
                <td style="width: 80px;">
                    <div class="cell-actions">
                        <button class="action-btn" title="Edit" onclick="RowModal.openEdit('${App.state.currentTable}', ${rowIdParam})">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                            </svg>
                        </button>
                        <button class="action-btn danger" title="Delete" onclick="RowModal.openDelete('${App.state.currentTable}', ${rowIdParam})">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            </svg>
                        </button>
                    </div>
                </td>
            </tr>
            `;
            return html;
        }).join('');

        // Row checkbox listeners
        document.querySelectorAll('.row-checkbox').forEach(cb => {
            cb.addEventListener('change', (e) => {
                const rowId = e.target.dataset.rowId;
                if (e.target.checked) {
                    App.state.selectedRows.push(rowId);
                } else {
                    App.state.selectedRows = App.state.selectedRows.filter(id => id !== rowId);
                }
            });
        });
    },

    /**
     * Render pagination
     */
    renderPagination(total, page, pageSize) {
        const pagination = document.getElementById('tablePagination');
        if (!pagination) return;

        const totalPages = Math.ceil(total / pageSize);
        const start = (page - 1) * pageSize + 1;
        const end = Math.min(page * pageSize, total);

        let pagesHtml = '';
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= page - 1 && i <= page + 1)) {
                pagesHtml += `
                    <button class="pagination-btn ${i === page ? 'active' : ''}" 
                            onclick="TableManager.loadTableData('${App.state.currentTable}', ${i})">
                        ${i}
                    </button>
                `;
            } else if (i === page - 2 || i === page + 2) {
                pagesHtml += `<span style="padding: 0 4px;">...</span>`;
            }
        }

        pagination.innerHTML = `
            <div class="pagination-info">
                Showing ${start} to ${end} of ${total} rows
            </div>
            <div class="pagination-controls">
                <button class="pagination-btn" onclick="TableManager.loadTableData('${App.state.currentTable}', ${page - 1})" ${page <= 1 ? 'disabled' : ''}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="15 18 9 12 15 6"></polyline>
                    </svg>
                </button>
                ${pagesHtml}
                <button class="pagination-btn" onclick="TableManager.loadTableData('${App.state.currentTable}', ${page + 1})" ${page >= totalPages ? 'disabled' : ''}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                </button>
            </div>
        `;
    },
};

// =============================================
// ROW MODAL OPERATIONS
// =============================================

const RowModal = {
    currentSchema: null,
    currentRowId: null,

    /**
     * Open add row modal
     */
    async openAdd(tableName) {
        try {
            const schema = await API.getTableSchema(tableName);
            this.currentSchema = schema;
            this.currentRowId = null;

            const formHtml = this.buildForm(schema.columns, {});
            document.getElementById('rowModalTitle').textContent = 'Add Row';
            document.getElementById('rowModalForm').innerHTML = formHtml;
            document.getElementById('rowModalSubmit').textContent = 'Insert Row';
            document.getElementById('rowModalSubmit').onclick = () => this.submitAdd(tableName);

            UI.openModal('rowModal');
        } catch (error) {
            UI.showToast('Failed to load table schema', 'error');
        }
    },

    /**
     * Open edit row modal
     */
    async openEdit(tableName, rowId) {
        try {
            const [schema, data] = await Promise.all([
                API.getTableSchema(tableName),
                API.getTableRows(tableName, { id: rowId }),
            ]);

            this.currentSchema = schema;
            this.currentRowId = rowId;

            const rowData = data.rows.find(r => (r.id || r.rowid) == rowId) || {};
            const formHtml = this.buildForm(schema.columns, rowData);

            document.getElementById('rowModalTitle').textContent = 'Edit Row';
            document.getElementById('rowModalForm').innerHTML = formHtml;
            document.getElementById('rowModalSubmit').textContent = 'Save Changes';
            document.getElementById('rowModalSubmit').onclick = () => this.submitEdit(tableName, rowId);

            UI.openModal('rowModal');
        } catch (error) {
            UI.showToast('Failed to load row data', 'error');
        }
    },

    /**
     * Build form HTML from schema
     */
    buildForm(columns, data) {
        return columns.map(col => {
            const value = data[col.name] !== undefined ? data[col.name] : '';
            const isRequired = col.notnull && !col.pk;
            const isDisabled = col.pk && data[col.name] !== undefined;

            let inputHtml = '';
            const inputType = this.getInputType(col.type);

            if (inputType === 'textarea') {
                inputHtml = `<textarea class="form-textarea" name="${col.name}" ${isRequired ? 'required' : ''} ${isDisabled ? 'disabled' : ''}>${UI.escapeHtml(String(value))}</textarea>`;
            } else if (inputType === 'checkbox') {
                inputHtml = `<input type="checkbox" name="${col.name}" ${value ? 'checked' : ''} ${isDisabled ? 'disabled' : ''}>`;
            } else {
                inputHtml = `<input type="${inputType}" class="form-input" name="${col.name}" value="${UI.escapeHtml(String(value))}" ${isRequired ? 'required' : ''} ${isDisabled ? 'disabled' : ''}>`;
            }

            return `
                <div class="form-group">
                    <label class="form-label">
                        ${UI.escapeHtml(col.name)}
                        ${isRequired ? '<span class="required">*</span>' : ''}
                    </label>
                    ${inputHtml}
                    <div class="form-hint">${col.type}${col.pk ? ' • Primary Key' : ''}${col.notnull ? ' • Not Null' : ''}</div>
                </div>
            `;
        }).join('');
    },

    /**
     * Get input type from column type
     */
    getInputType(colType) {
        const type = colType.toUpperCase();
        if (type.includes('INT')) return 'number';
        if (type.includes('REAL') || type.includes('FLOAT') || type.includes('DOUBLE')) return 'number';
        if (type.includes('BOOL')) return 'checkbox';
        if (type.includes('DATE') && !type.includes('TIME')) return 'date';
        if (type.includes('TIME') && !type.includes('DATE')) return 'time';
        if (type.includes('DATETIME') || type.includes('TIMESTAMP')) return 'datetime-local';
        if (type.includes('TEXT') || type.includes('BLOB')) return 'textarea';
        return 'text';
    },

    /**
     * Submit add row
     */
    async submitAdd(tableName) {
        const form = document.getElementById('rowModalForm');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        // Handle checkboxes
        this.currentSchema.columns.forEach(col => {
            if (this.getInputType(col.type) === 'checkbox') {
                data[col.name] = form.querySelector(`[name="${col.name}"]`).checked;
            }
        });

        try {
            await API.insertRow(tableName, data);
            UI.showToast('Row inserted successfully');
            UI.closeModal('rowModal');
            TableManager.loadTableData(tableName);
        } catch (error) {
            UI.showToast(error.message || 'Failed to insert row', 'error');
        }
    },

    /**
     * Submit edit row
     */
    async submitEdit(tableName, rowId) {
        const form = document.getElementById('rowModalForm');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        // Handle checkboxes
        this.currentSchema.columns.forEach(col => {
            if (this.getInputType(col.type) === 'checkbox') {
                data[col.name] = form.querySelector(`[name="${col.name}"]`).checked;
            }
        });

        try {
            await API.updateRow(tableName, rowId, data);
            UI.showToast('Row updated successfully');
            UI.closeModal('rowModal');
            TableManager.loadTableData(tableName);
        } catch (error) {
            UI.showToast(error.message || 'Failed to update row', 'error');
        }
    },

    /**
     * Open delete confirmation
     */
    openDelete(tableName, rowId) {
        this.currentRowId = rowId;
        document.getElementById('deleteModalConfirm').onclick = () => this.confirmDelete(tableName, rowId);
        UI.openModal('deleteModal');
    },

    /**
     * Confirm delete
     */
    async confirmDelete(tableName, rowId) {
        try {
            await API.deleteRow(tableName, rowId);
            UI.showToast('Row deleted successfully');
            UI.closeModal('deleteModal');
            TableManager.loadTableData(tableName);
        } catch (error) {
            UI.showToast(error.message || 'Failed to delete row', 'error');
        }
    },
};

// =============================================
// CREATE TABLE
// =============================================

const CreateTable = {
    columnCount: 0,

    /**
     * Initialize create table form
     */
    init() {
        const container = document.getElementById('columnsContainer');
        if (!container) return;

        this.columnCount = 0;
        this.addColumn();
    },

    /**
     * Add a new column definition
     */
    addColumn() {
        const container = document.getElementById('columnsContainer');
        if (!container) return;

        const columnId = this.columnCount++;
        const columnHtml = `
            <div class="column-definition" id="column-${columnId}">
                <div class="form-group column-name">
                    <label class="form-label">Column Name</label>
                    <input type="text" class="form-input" name="col_name_${columnId}" placeholder="e.g. user_id" required>
                </div>
                <div class="form-group column-type">
                    <label class="form-label">Type</label>
                    <select class="form-select" name="col_type_${columnId}">
                        <option value="INTEGER">INTEGER</option>
                        <option value="TEXT">TEXT</option>
                        <option value="REAL">REAL</option>
                        <option value="BLOB">BLOB</option>
                        <option value="BOOLEAN">BOOLEAN</option>
                        <option value="DATETIME">DATETIME</option>
                    </select>
                </div>
                <div class="column-constraints">
                    <label>
                        <input type="checkbox" name="col_pk_${columnId}">
                        Primary Key
                    </label>
                    <label>
                        <input type="checkbox" name="col_notnull_${columnId}">
                        Not Null
                    </label>
                    <label>
                        <input type="checkbox" name="col_unique_${columnId}">
                        Unique
                    </label>
                </div>
                <div class="remove-column-btn">
                    <button type="button" onclick="CreateTable.removeColumn(${columnId})" ${columnId === 0 ? 'style="visibility:hidden"' : ''}>
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>
            </div>
        `;

        // Insert before add button
        const addBtn = container.querySelector('.add-column-btn');
        if (addBtn) {
            addBtn.insertAdjacentHTML('beforebegin', columnHtml);
        } else {
            container.innerHTML += columnHtml;
        }
    },

    /**
     * Remove column
     */
    removeColumn(columnId) {
        const column = document.getElementById(`column-${columnId}`);
        if (column) {
            column.remove();
        }
    },

    /**
     * Submit create table form
     */
    async submit(event) {
        event.preventDefault();

        const tableName = document.getElementById('tableName').value.trim();
        if (!tableName) {
            UI.showToast('Table name is required', 'error');
            return;
        }

        const columns = [];
        const columnElements = document.querySelectorAll('.column-definition');

        columnElements.forEach((el, index) => {
            const id = el.id.replace('column-', '');
            const name = el.querySelector(`[name="col_name_${id}"]`)?.value.trim();
            const type = el.querySelector(`[name="col_type_${id}"]`)?.value;
            const pk = el.querySelector(`[name="col_pk_${id}"]`)?.checked;
            const notnull = el.querySelector(`[name="col_notnull_${id}"]`)?.checked;
            const unique = el.querySelector(`[name="col_unique_${id}"]`)?.checked;

            if (name) {
                columns.push({ name, type, pk, notnull, unique });
            }
        });

        if (columns.length === 0) {
            UI.showToast('At least one column is required', 'error');
            return;
        }

        try {
            await API.createTable({ name: tableName, columns });
            UI.showToast(`Table "${tableName}" created successfully`);
            window.location.href = `/table/${tableName}/`;
        } catch (error) {
            UI.showToast(error.message || 'Failed to create table', 'error');
        }
    },
};

// =============================================
// FILTER MANAGER
// =============================================

const FilterManager = {
    isOpen: false,

    /**
     * Toggle filter dropdown
     */
    toggle() {
        const dropdown = document.getElementById('filterDropdown');
        if (!dropdown) return;

        this.isOpen = !this.isOpen;
        dropdown.classList.toggle('active', this.isOpen);
    },

    /**
     * Add filter
     */
    addFilter() {
        App.state.filters.push({
            column: '',
            operator: 'eq',
            value: '',
        });
        this.render();
    },

    /**
     * Remove filter
     */
    removeFilter(index) {
        App.state.filters.splice(index, 1);
        this.render();
    },

    /**
     * Apply filters
     */
    apply() {
        this.isOpen = false;
        document.getElementById('filterDropdown')?.classList.remove('active');
        TableManager.loadTableData(App.state.currentTable);
    },

    /**
     * Clear all filters
     */
    clear() {
        App.state.filters = [];
        this.render();
        TableManager.loadTableData(App.state.currentTable);
    },

    /**
     * Render filter UI
     */
    render() {
        const container = document.getElementById('filterContainer');
        if (!container) return;

        if (App.state.filters.length === 0) {
            container.innerHTML = '<p class="text-muted" style="font-size: 13px;">No filters applied</p>';
            return;
        }

        // Get columns from current schema
        const columns = App.state.tables.find(t => t.name === App.state.currentTable)?.columns || [];

        container.innerHTML = App.state.filters.map((filter, index) => `
            <div class="filter-row">
                <select class="form-select" style="flex: 1;" onchange="FilterManager.updateFilter(${index}, 'column', this.value)">
                    <option value="">Column</option>
                    ${columns.map(col => `<option value="${col}" ${filter.column === col ? 'selected' : ''}>${col}</option>`).join('')}
                </select>
                <select class="form-select" style="width: 80px;" onchange="FilterManager.updateFilter(${index}, 'operator', this.value)">
                    <option value="eq" ${filter.operator === 'eq' ? 'selected' : ''}>=</option>
                    <option value="neq" ${filter.operator === 'neq' ? 'selected' : ''}>≠</option>
                    <option value="gt" ${filter.operator === 'gt' ? 'selected' : ''}>></option>
                    <option value="lt" ${filter.operator === 'lt' ? 'selected' : ''}><</option>
                    <option value="like" ${filter.operator === 'like' ? 'selected' : ''}>Like</option>
                </select>
                <input type="text" class="form-input" style="flex: 1;" placeholder="Value" value="${filter.value}" onchange="FilterManager.updateFilter(${index}, 'value', this.value)">
                <button class="action-btn danger" onclick="FilterManager.removeFilter(${index})">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
        `).join('');
    },

    /**
     * Update filter value
     */
    updateFilter(index, key, value) {
        if (App.state.filters[index]) {
            App.state.filters[index][key] = value;
        }
    },
};

// =============================================
// SEARCH
// =============================================

const Search = {
    debounceTimer: null,

    /**
     * Handle search input
     */
    handleInput(value) {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
            if (value.length >= 2) {
                App.state.filters = [{
                    column: '_search',
                    operator: 'like',
                    value: value,
                }];
            } else {
                App.state.filters = [];
            }
            TableManager.loadTableData(App.state.currentTable);
        }, 300);
    },
};

// =============================================
// INITIALIZATION
// =============================================

document.addEventListener('DOMContentLoaded', () => {
    // Load tables list
    TableManager.loadTablesList();

    // Sidebar toggle (mobile)
    document.getElementById('sidebarToggle')?.addEventListener('click', () => {
        document.getElementById('sidebar')?.classList.toggle('active');
    });

    // Refresh button
    document.getElementById('refreshBtn')?.addEventListener('click', () => {
        if (App.state.currentTable) {
            TableManager.loadTableData(App.state.currentTable);
        }
        TableManager.loadTablesList();
    });

    // Close modals on overlay click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                UI.closeAllModals();
            }
        });
    });

    // Close modals on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            UI.closeAllModals();
        }
    });

    // Initialize create table form if on that page
    if (document.getElementById('createTableForm')) {
        CreateTable.init();
    }
});

// Export for global access
window.App = App;
window.API = API;
window.UI = UI;
window.TableManager = TableManager;
window.RowModal = RowModal;
window.CreateTable = CreateTable;
window.FilterManager = FilterManager;
window.Search = Search;
