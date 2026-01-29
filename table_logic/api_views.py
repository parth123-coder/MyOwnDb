"""
Public API views for external access (v1).
Uses API Key authentication instead of session-based auth.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import connection

from .authentication import APIKeyAuthentication
from .models import UserTable, ActivityLog, APIKey


def log_api_activity(user, action, table_name, description, metadata=None, request=None):
    """Log API activity with source marked as 'API'"""
    ip_address = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
    
    # Add API source to metadata
    if metadata is None:
        metadata = {}
    metadata['source'] = 'api'
    if hasattr(request, 'auth') and isinstance(request.auth, APIKey):
        metadata['api_key_name'] = request.auth.name
    
    ActivityLog.objects.create(
        user=user,
        action=action,
        table_name=table_name,
        description=description,
        metadata=metadata,
        ip_address=ip_address
    )


# =============================================
# PUBLIC API VIEWS (API Key Auth)
# =============================================

class PublicTableListView(APIView):
    """
    GET: List all tables for the authenticated user.
    
    Headers:
        X-API-Key: sk_your_key_here
    
    Response:
        [
            {"name": "products", "row_count": 150},
            {"name": "orders", "row_count": 42}
        ]
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        tables = UserTable.objects.filter(user=request.user)
        result = []
        
        for table in tables:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table.real_name}"')
                    row_count = cursor.fetchone()[0]
            except:
                row_count = 0
            
            result.append({
                'name': table.table_name,
                'row_count': row_count,
                'created_at': table.created_at.isoformat(),
            })
        
        return Response({
            'success': True,
            'tables': result,
            'count': len(result),
        })

    def post(self, request):
        """Create a new table"""
        name = request.data.get('name')
        columns = request.data.get('columns', [])
        
        if not name or not columns:
            return Response({'success': False, 'error': 'Name and columns are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Copied logic from TableListCreateView.post
        if UserTable.objects.filter(user=request.user, table_name=name).exists():
            return Response({'success': False, 'error': f'Table "{name}" already exists'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate unique real table name
        real_name = f"u{request.user.id}_{name}"
        
        # Build CREATE TABLE SQL
        column_defs = []
        for col in columns:
            col_name = col.get('name', '').strip()
            col_type = col.get('type', 'TEXT').upper()
            
            # Basic sanitization
            if not col_name.isidentifier(): 
                 return Response({'success': False, 'error': f'Invalid column name: {col_name}'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Determine mapping
            if connection.vendor != 'sqlite':
                if col_type == 'BLOB': col_type = 'BYTEA'
                elif col_type == 'DATETIME': col_type = 'TIMESTAMP'

            # Primary Key?
            # We don't support complex PK config via this simple API for now, assume standard config
            # Or trust the input since it's authenticated
            col_def = f'"{col_name}" {col_type}'
            column_defs.append(col_def)
        
        # Fallback if no columns? SQLite needs at least one.
        if not column_defs:
             return Response({'success': False, 'error': 'At least one column required'}, status=status.HTTP_400_BAD_REQUEST)

        sql = f'CREATE TABLE "{real_name}" ({", ".join(column_defs)})'
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
            
            UserTable.objects.create(
                user=request.user,
                table_name=name,
                real_name=real_name,
                schema=columns
            )
            
            log_api_activity(request.user, 'CREATE_TABLE', name, f'Created table "{name}" via API', request=request)
            
            return Response({
                'success': True,
                'message': f'Table "{name}" created successfully'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicTableDetailView(APIView):
    """
    GET: Get table schema and info.
    
    Headers:
        X-API-Key: sk_your_key_here
    
    Response:
        {
            "name": "products",
            "columns": [...],
            "row_count": 150
        }
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, table_name):
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT COUNT(*) FROM "{user_table.real_name}"')
                row_count = cursor.fetchone()[0]
        except:
            row_count = 0
        
        return Response({
            'success': True,
            'name': table_name,
            'columns': user_table.schema,
            'row_count': row_count,
            'created_at': user_table.created_at.isoformat(),
        })


class PublicTableRowsView(APIView):
    """
    GET: Get rows from a table with pagination.
    POST: Insert a new row.
    
    Headers:
        X-API-Key: sk_your_key_here
    
    GET Parameters:
        page (int): Page number (default: 1)
        limit (int): Rows per page (default: 25, max: 100)
        sort (str): Column to sort by
        order (str): 'asc' or 'desc'
    
    POST Body:
        {"column1": "value1", "column2": "value2"}
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, table_name):
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Parse query params
        try:
            page = int(request.query_params.get('page', 1))
            limit = min(int(request.query_params.get('limit', 25)), 100)
            offset = int(request.query_params.get('offset', (page - 1) * limit))
            sort = request.query_params.get('sort', '')
            order = request.query_params.get('order', 'asc').lower()
            if order not in ['asc', 'desc']:
                order = 'asc'
            search = request.query_params.get('search', '').strip()
            
            with connection.cursor() as cursor:
                schema_columns = [col.get('name') for col in user_table.schema]
                
                # Build WHERE clause
                where_clauses = []
                params = []
                
                # 1. Search
                if search:
                    search_conditions = []
                    # Search all columns that look like text? Or just convert everything to text
                    for col in schema_columns:
                        search_conditions.append(f'CAST("{col}" AS TEXT) LIKE %s')
                        params.append(f'%{search}%')
                    if search_conditions:
                        where_clauses.append(f"({' OR '.join(search_conditions)})")

                # 2. Filters (col=val, col__gt=val, etc)
                # Operators map: suffix -> sql op
                operators = {
                    '': '=',
                    'gt': '>',
                    'lt': '<',
                    'gte': '>=',
                    'lte': '<=',
                    'ne': '!=',
                    'contains': 'LIKE',
                    'icontains': 'ILIKE',
                }
                
                for key, value in request.query_params.items():
                    # Skip reserved keys
                    if key in ['page', 'limit', 'offset', 'sort', 'order', 'search']:
                        continue
                        
                    # Check for operator suffix
                    parts = key.split('__')
                    col_name = parts[0]
                    op_suffix = parts[1] if len(parts) > 1 else ''
                    
                    if col_name in schema_columns and op_suffix in operators:
                        operator = operators[op_suffix]
                        
                        # Handle LIKE wildcards if not present
                        if 'contains' in op_suffix and '%' not in value:
                            value = f'%{value}%'
                            
                        # SQLite doesn't support ILIKE standardly (though some builds do)
                        # Fallback for SQLite to Upper() = Upper() if needed, but LIKE is case insensitive in SQLite default for ASCII
                        if connection.vendor == 'sqlite' and operator == 'ILIKE':
                            operator = 'LIKE' 

                        where_clauses.append(f'"{col_name}" {operator} %s')
                        params.append(value)

                where_sql = ""
                if where_clauses:
                    where_sql = "WHERE " + " AND ".join(where_clauses)

                # Build ORDER BY clause
                order_clause = ""
                if sort and sort in schema_columns:
                    order_direction = "DESC" if order == "desc" else "ASC"
                    order_clause = f'ORDER BY "{sort}" {order_direction}'
                
                # Get total count
                count_sql = f'SELECT COUNT(*) FROM "{user_table.real_name}" {where_sql}'
                cursor.execute(count_sql, params)
                total = cursor.fetchone()[0]
                
                # Get rows
                # SQLite Needs rowid selected explicitly if we want to use it for updates later
                rows_sql = f'SELECT *, rowid FROM "{user_table.real_name}" {where_sql} {order_clause} LIMIT {limit} OFFSET {offset}'
                cursor.execute(rows_sql, params)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return Response({
                'success': True,
                'rows': rows,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit if limit > 0 else 0,
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, table_name):
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            data = request.data
            if not data:
                return Response({
                    'success': False,
                    'error': 'Request body is empty'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            columns = list(data.keys())
            values = list(data.values())
            placeholders = ', '.join(['%s' for _ in values])
            columns_str = ', '.join([f'"{col}"' for col in columns])
            
            sql = f'INSERT INTO "{user_table.real_name}" ({columns_str}) VALUES ({placeholders})'
            
            if connection.vendor == 'postgresql':
                # Find PK column
                pk_col = 'id'
                for col in user_table.schema:
                    if col.get('pk'):
                        pk_col = col.get('name')
                        break
                        
                sql += f' RETURNING "{pk_col}"'
                with connection.cursor() as cursor:
                    cursor.execute(sql, values)
                    row_id = cursor.fetchone()[0]
            else:
                with connection.cursor() as cursor:
                    cursor.execute(sql, values)
                    row_id = cursor.lastrowid
            
            # Log activity
            log_api_activity(
                user=request.user,
                action='INSERT_ROW',
                table_name=table_name,
                description=f'Inserted row via API into "{table_name}"',
                metadata={'row_id': row_id, 'data': data},
                request=request
            )
            
            return Response({
                'success': True,
                'message': 'Row inserted',
                'id': row_id
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicTableRowDetailView(APIView):
    """
    GET: Get a single row by ID.
    PUT: Update a row.
    DELETE: Delete a row.
    
    Headers:
        X-API-Key: sk_your_key_here
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, table_name, row_id):
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT *, rowid FROM "{user_table.real_name}" WHERE rowid = %s', [row_id])
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                row = cursor.fetchone()
                
                if not row:
                    return Response({
                        'success': False,
                        'error': 'Row not found'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                return Response({
                    'success': True,
                    'row': dict(zip(columns, row))
                })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, table_name, row_id):
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            data = request.data
            if not data:
                return Response({
                    'success': False,
                    'error': 'Request body is empty'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            set_clause_parts = []
            values = []
            for col, val in data.items():
                set_clause_parts.append(f'"{col}" = %s')
                values.append(val)
            
            set_clause = ', '.join(set_clause_parts)
            values.append(row_id)
            
            sql = f'UPDATE "{user_table.real_name}" SET {set_clause} WHERE rowid = %s'
            
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                updated = cursor.rowcount
            
            if updated == 0:
                return Response({
                    'success': False,
                    'error': 'Row not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Log activity
            log_api_activity(
                user=request.user,
                action='UPDATE_ROW',
                table_name=table_name,
                description=f'Updated row {row_id} via API in "{table_name}"',
                metadata={'row_id': row_id, 'updated_fields': list(data.keys())},
                request=request
            )
            
            return Response({
                'success': True,
                'message': 'Row updated'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, table_name, row_id):
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'DELETE FROM "{user_table.real_name}" WHERE rowid = %s', [row_id])
                deleted = cursor.rowcount
            
            if deleted == 0:
                return Response({
                    'success': False,
                    'error': 'Row not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Log activity
            log_api_activity(
                user=request.user,
                action='DELETE_ROW',
                table_name=table_name,
                description=f'Deleted row {row_id} via API from "{table_name}"',
                metadata={'row_id': row_id},
                request=request
            )
            
            return Response({
                'success': True,
                'message': 'Row deleted'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicTableColumnsView(APIView):
    """
    POST: Add a column to the table
    PUT: Rename a column
    DELETE: Delete a column
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, table_name):
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({'success': False, 'error': 'Table not found'}, status=status.HTTP_404_NOT_FOUND)
            
        col_name = request.data.get('name')
        col_type = request.data.get('type', 'TEXT').upper()
        
        if not col_name:
            return Response({'success': False, 'error': 'Column name is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Validate column name 
        if not col_name.isidentifier():
             return Response({'success': False, 'error': 'Invalid column name'}, status=status.HTTP_400_BAD_REQUEST)
             
        # Check if already exists
        existing_cols = [c['name'] for c in user_table.schema]
        if col_name in existing_cols:
             return Response({'success': False, 'error': 'Column already exists'}, status=status.HTTP_400_BAD_REQUEST)
             
        real_type = col_type
        if connection.vendor != 'sqlite':
            if real_type == 'BLOB': real_type = 'BYTEA'
            elif real_type == 'DATETIME': real_type = 'TIMESTAMP'

        sql = f'ALTER TABLE "{user_table.real_name}" ADD COLUMN "{col_name}" {real_type}'
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                
            # Update Schema
            user_table.schema.append({'name': col_name, 'type': col_type})
            user_table.save(update_fields=['schema'])
            
            log_api_activity(request.user, 'ADD_COLUMN', table_name, f'Added column "{col_name}" to "{table_name}"', request=request)
            
            return Response({'success': True, 'message': f'Column "{col_name}" added'})
        except Exception as e:
             return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, table_name):
        """Rename a column"""
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({'success': False, 'error': 'Table not found'}, status=status.HTTP_404_NOT_FOUND)
        
        old_name = request.data.get('old_name')
        new_name = request.data.get('new_name')
        
        if not old_name or not new_name:
            return Response({'success': False, 'error': 'old_name and new_name are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate new column name
        if not new_name.isidentifier():
            return Response({'success': False, 'error': 'Invalid new column name'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if old column exists
        existing_cols = {c['name']: c for c in user_table.schema}
        if old_name not in existing_cols:
            return Response({'success': False, 'error': f'Column "{old_name}" not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if new name already exists
        if new_name in existing_cols and new_name != old_name:
            return Response({'success': False, 'error': f'Column "{new_name}" already exists'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with connection.cursor() as cursor:
                if connection.vendor == 'postgresql':
                    sql = f'ALTER TABLE "{user_table.real_name}" RENAME COLUMN "{old_name}" TO "{new_name}"'
                    cursor.execute(sql)
                else:
                    # SQLite supports RENAME COLUMN since version 3.25.0
                    sql = f'ALTER TABLE "{user_table.real_name}" RENAME COLUMN "{old_name}" TO "{new_name}"'
                    cursor.execute(sql)
            
            # Update schema
            for col in user_table.schema:
                if col['name'] == old_name:
                    col['name'] = new_name
                    break
            user_table.save(update_fields=['schema'])
            
            log_api_activity(request.user, 'RENAME_COLUMN', table_name, f'Renamed column "{old_name}" to "{new_name}" in "{table_name}"', request=request)
            
            return Response({'success': True, 'message': f'Column renamed from "{old_name}" to "{new_name}"'})
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, table_name):
        """Delete a column"""
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({'success': False, 'error': 'Table not found'}, status=status.HTTP_404_NOT_FOUND)
        
        col_name = request.data.get('name')
        
        if not col_name:
            return Response({'success': False, 'error': 'Column name is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if column exists
        existing_cols = [c['name'] for c in user_table.schema]
        if col_name not in existing_cols:
            return Response({'success': False, 'error': f'Column "{col_name}" not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Prevent deleting last column
        if len(existing_cols) <= 1:
            return Response({'success': False, 'error': 'Cannot delete the last column'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with connection.cursor() as cursor:
                if connection.vendor == 'postgresql':
                    sql = f'ALTER TABLE "{user_table.real_name}" DROP COLUMN "{col_name}"'
                    cursor.execute(sql)
                else:
                    # SQLite DROP COLUMN supported since 3.35.0
                    # Try it first, fall back to table recreation if it fails
                    try:
                        sql = f'ALTER TABLE "{user_table.real_name}" DROP COLUMN "{col_name}"'
                        cursor.execute(sql)
                    except Exception:
                        # Fallback: recreate table without the column (for older SQLite)
                        remaining_cols = [c for c in user_table.schema if c['name'] != col_name]
                        cols_str = ', '.join([f'"{c["name"]}"' for c in remaining_cols])
                        
                        # Create temp table, copy data, drop old, rename
                        temp_name = f"{user_table.real_name}_temp"
                        col_defs = ', '.join([f'"{c["name"]}" {c.get("type", "TEXT")}' for c in remaining_cols])
                        
                        cursor.execute(f'CREATE TABLE "{temp_name}" ({col_defs})')
                        cursor.execute(f'INSERT INTO "{temp_name}" ({cols_str}) SELECT {cols_str} FROM "{user_table.real_name}"')
                        cursor.execute(f'DROP TABLE "{user_table.real_name}"')
                        cursor.execute(f'ALTER TABLE "{temp_name}" RENAME TO "{user_table.real_name}"')
            
            # Update schema
            user_table.schema = [c for c in user_table.schema if c['name'] != col_name]
            user_table.save(update_fields=['schema'])
            
            log_api_activity(request.user, 'DELETE_COLUMN', table_name, f'Deleted column "{col_name}" from "{table_name}"', request=request)
            
            return Response({'success': True, 'message': f'Column "{col_name}" deleted'})
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================
# API KEY MANAGEMENT VIEWS (Session Auth)
# =============================================

class APIKeyListCreateView(APIView):
    """
    GET: List all API keys for current user.
    POST: Create a new API key.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        keys = APIKey.objects.filter(user=request.user)
        result = []
        
        for key in keys:
            result.append({
                'id': key.id,
                'name': key.name,
                'key_prefix': key.key_prefix,
                'created_at': key.created_at.isoformat(),
                'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None,
                'is_active': key.is_active,
            })
        
        return Response({
            'success': True,
            'keys': result,
            'count': len(result),
        })
    
    def post(self, request):
        name = request.data.get('name', '').strip()
        
        if not name:
            return Response({
                'success': False,
                'error': 'Key name is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create the key
        api_key, raw_key = APIKey.create_key(user=request.user, name=name)
        
        return Response({
            'success': True,
            'message': 'API key created. Copy it now - it will not be shown again!',
            'key': raw_key,  # Only time the raw key is returned!
            'id': api_key.id,
            'name': api_key.name,
            'key_prefix': api_key.key_prefix,
        }, status=status.HTTP_201_CREATED)


class APIKeyDetailView(APIView):
    """
    DELETE: Revoke/delete an API key.
    PATCH: Update key status (activate/deactivate).
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, key_id):
        try:
            api_key = APIKey.objects.get(id=key_id, user=request.user)
            api_key.delete()
            
            return Response({
                'success': True,
                'message': 'API key deleted'
            })
        except APIKey.DoesNotExist:
            return Response({
                'success': False,
                'error': 'API key not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def patch(self, request, key_id):
        try:
            api_key = APIKey.objects.get(id=key_id, user=request.user)
            
            is_active = request.data.get('is_active')
            if is_active is not None:
                api_key.is_active = is_active
                api_key.save(update_fields=['is_active'])
            
            return Response({
                'success': True,
                'message': f'API key {"activated" if api_key.is_active else "deactivated"}'
            })
        except APIKey.DoesNotExist:
            return Response({
                'success': False,
                'error': 'API key not found'
            }, status=status.HTTP_404_NOT_FOUND)
