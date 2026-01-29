from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import connection
from django.core.paginator import Paginator

from .models import UserTable, ActivityLog
from .serializers import CreateTableSerializer


# ============================================
# ACTIVITY LOGGING HELPER
# ============================================
def log_activity(user, action, table_name, description, metadata=None, request=None):
    """
    Helper function to log user activities.
    
    Actions: CREATE_TABLE, DELETE_TABLE, INSERT_ROW, UPDATE_ROW, DELETE_ROW
    """
    ip_address = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
    
    ActivityLog.objects.create(
        user=user,
        action=action,
        table_name=table_name,
        description=description,
        metadata=metadata,
        ip_address=ip_address
    )


class TableListCreateView(APIView):
    """
    GET: List all tables for current user
    POST: Create a new table
    """
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
            })
        
        return Response(result)

    def post(self, request):
        # Debug: Print received data
        print("=" * 50)
        print("RECEIVED DATA:", request.data)
        print("=" * 50)
        
        serializer = CreateTableSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        table_name = serializer.validated_data['name']
        columns = serializer.validated_data['columns']
        
        # Check if table already exists for this user
        if UserTable.objects.filter(user=request.user, table_name=table_name).exists():
            return Response({
                'success': False,
                'error': f'Table "{table_name}" already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate: Only one primary key allowed
        pk_count = sum(1 for col in columns if col.get('pk') in [True, 'true', 'True', 1, '1'])
        if pk_count > 1:
            return Response({
                'success': False,
                'error': 'Only one column can be set as Primary Key'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate unique real table name
        real_name = f"u{request.user.id}_{table_name}"
        
        # Build CREATE TABLE SQL
        column_defs = []
        for col in columns:
            col_name = col.get('name', '').strip()
            col_type = col.get('type', 'TEXT').upper()
            
            # Handle boolean values (could be string 'true'/'false' or actual boolean)
            is_pk = col.get('pk') in [True, 'true', 'True', 1, '1']
            is_notnull = col.get('notnull') in [True, 'true', 'True', 1, '1']
            is_unique = col.get('unique') in [True, 'true', 'True', 1, '1']
            
            # Build column definition
            # Map types for PostgreSQL
            if connection.vendor != 'sqlite':
                if col_type == 'BLOB':
                    col_type = 'BYTEA'
                elif col_type == 'DATETIME':
                    col_type = 'TIMESTAMP'

            # Build column definition
            if is_pk:
                if connection.vendor == 'sqlite':
                    if col_type == 'INTEGER':
                        # SQLite requires exact syntax for auto-increment
                        col_def = f'"{col_name}" INTEGER PRIMARY KEY AUTOINCREMENT'
                    else:
                        col_def = f'"{col_name}" {col_type} PRIMARY KEY'
                else:
                    # PostgreSQL
                    if col_type == 'INTEGER':
                        # SERIAL implies INTEGER + AUTOINCREMENT + PRIMARY KEY (implied) + NOT NULL
                        col_def = f'"{col_name}" SERIAL PRIMARY KEY'
                    else:
                        col_def = f'"{col_name}" {col_type} PRIMARY KEY'
            else:
                col_def = f'"{col_name}" {col_type}'
                if is_notnull:
                    col_def += ' NOT NULL'
                if is_unique:
                    col_def += ' UNIQUE'
            
            column_defs.append(col_def)
        
        sql = f'CREATE TABLE "{real_name}" ({", ".join(column_defs)})'
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
            
            UserTable.objects.create(
                user=request.user,
                table_name=table_name,
                real_name=real_name,
                schema=columns
            )
            
            # Log activity
            log_activity(
                user=request.user,
                action='CREATE_TABLE',
                table_name=table_name,
                description=f'Created table "{table_name}" with {len(columns)} columns',
                metadata={'columns': [col.get('name') for col in columns]},
                request=request
            )
            
            return Response({
                'success': True,
                'message': f'Table "{table_name}" created successfully'
            }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            # Log the SQL for debugging
            print(f"SQL Error: {sql}")
            print(f"Error: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TableDetailView(APIView):
    """
    DELETE: Drop a table
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, table_name):
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'DROP TABLE IF EXISTS "{user_table.real_name}"')
            user_table.delete()
            
            # Log activity
            log_activity(
                user=request.user,
                action='DELETE_TABLE',
                table_name=table_name,
                description=f'Deleted table "{table_name}"',
                request=request
            )
            
            return Response({
                'success': True,
                'message': f'Table "{table_name}" deleted'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TableSchemaView(APIView):
    """
    GET: Get table schema
    """
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
            'table_name': table_name,
            'row_count': row_count,
            'columns': user_table.schema,
        })


class TableRowsView(APIView):
    """
    GET: Get rows with pagination and search
    POST: Insert a new row
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, table_name):
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 25))
        search = request.query_params.get('search', '').strip()
        sort = request.query_params.get('sort', '')
        order = request.query_params.get('order', 'asc').lower()
        offset = (page - 1) * page_size
        
        try:
            with connection.cursor() as cursor:
                # Get column names from schema
                schema_columns = [col.get('name') for col in user_table.schema]
                
                # Build WHERE clause for search
                where_clause = ""
                params = []
                
                if search:
                    # Search across all text columns
                    search_conditions = []
                    for col in schema_columns:
                        search_conditions.append(f'CAST("{col}" AS TEXT) LIKE ?')
                        params.append(f'%{search}%')
                    where_clause = f"WHERE ({' OR '.join(search_conditions)})"
                
                # Check for column-specific filters
                for col in schema_columns:
                    filter_value = request.query_params.get(col)
                    if filter_value:
                        if where_clause:
                            where_clause += f' AND "{col}" LIKE ?'
                        else:
                            where_clause = f'WHERE "{col}" LIKE ?'
                        params.append(f'%{filter_value}%')
                
                # Build ORDER BY clause
                order_clause = ""
                if sort and sort in schema_columns:
                    order_direction = "DESC" if order == "desc" else "ASC"
                    order_clause = f'ORDER BY "{sort}" {order_direction}'
                
                # Get total count with filters
                count_sql = f'SELECT COUNT(*) FROM "{user_table.real_name}" {where_clause}'
                cursor.execute(count_sql, params)
                total = cursor.fetchone()[0]
                
                # Get rows with pagination
                if connection.vendor == 'sqlite':
                    # SQLite: Explicitly select rowid
                    rows_sql = f'SELECT *, rowid FROM "{user_table.real_name}" {where_clause} {order_clause} LIMIT {page_size} OFFSET {offset}'
                else:
                    # PostgreSQL: No rowid column, just select all
                    rows_sql = f'SELECT * FROM "{user_table.real_name}" {where_clause} {order_clause} LIMIT {page_size} OFFSET {offset}'
                
                cursor.execute(rows_sql, params)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return Response({
                'rows': rows,
                'total': total,
                'page': page,
                'page_size': page_size,
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
            print(f"INSERT DATA: {data}")  # Debug
            
            columns = list(data.keys())
            values = list(data.values())
            placeholders = ', '.join(['%s' for _ in values])
            columns_str = ', '.join([f'"{col}"' for col in columns])
            
            sql = f'INSERT INTO "{user_table.real_name}" ({columns_str}) VALUES ({placeholders})'
            print(f"INSERT SQL: {sql}")  # Debug
            print(f"VALUES: {values}")  # Debug
            
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
                    new_row_id = cursor.fetchone()[0]
            else:
                with connection.cursor() as cursor:
                    cursor.execute(sql, values)
                    new_row_id = cursor.lastrowid
            
            # Log activity
            log_activity(
                user=request.user,
                action='INSERT_ROW',
                table_name=table_name,
                description=f'Inserted new row in "{table_name}"',
                metadata={'row_id': new_row_id, 'data': data},
                request=request
            )
            
            return Response({
                'success': True,
                'message': 'Row inserted',
                'id': new_row_id
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(f"INSERT ERROR: {str(e)}")  # Debug
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TableRowDetailView(APIView):
    """
    PUT: Update a row
    DELETE: Delete a row
    """
    permission_classes = [IsAuthenticated]

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
            
            # Determine if we should use rowid or pk_col
            use_rowid = str(row_id).isdigit()
            if connection.vendor != 'sqlite':
                use_rowid = False
            
            # Prepare set clause
            # We must use %s for values to prevent SQL injection
            set_clause_parts = []
            values = []
            for col, val in data.items():
                set_clause_parts.append(f'"{col}" = %s')
                values.append(val)
            
            set_clause = ', '.join(set_clause_parts)
            values.append(row_id) # Add row_id for the WHERE clause
            
            if use_rowid:
                sql = f'UPDATE "{user_table.real_name}" SET {set_clause} WHERE rowid = %s'
            else:
                # Find primary key column name from schema
                pk_col = 'id' # Default
                for col in user_table.schema:
                    if col.get('pk'):
                        pk_col = col.get('name')
                        break
                sql = f'UPDATE "{user_table.real_name}" SET {set_clause} WHERE "{pk_col}" = %s'
            
            print(f"DEBUG UPDATE: Table={user_table.real_name}, UseRowID={use_rowid}, ID={row_id}")
            print(f"DEBUG SQL: {sql}")

            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                updated_count = cursor.rowcount
                print(f"DEBUG RESULT: Updated {updated_count} rows")
                
            # Retry logic if rowid failed
            if updated_count == 0 and use_rowid:
                 # Find primary key column name just in case
                pk_col = 'id'
                for col in user_table.schema:
                    if col.get('pk'):
                        pk_col = col.get('name')
                        break
                
                if pk_col.lower() != 'rowid':
                     sql_retry = f'UPDATE "{user_table.real_name}" SET {set_clause} WHERE "{pk_col}" = %s'
                     print(f"DEBUG RETRY: {sql_retry}")
                     with connection.cursor() as cursor:
                        cursor.execute(sql_retry, values) # values already has row_id at end
            
            # Log activity
            log_activity(
                user=request.user,
                action='UPDATE_ROW',
                table_name=table_name,
                description=f'Updated row {row_id} in "{table_name}"',
                metadata={'row_id': row_id, 'updated_fields': list(data.keys())},
                request=request
            )
            
            return Response({
                'success': True,
                'message': 'Row updated'
            })
        except Exception as e:
            print(f"UPDATE ERROR: {e}")
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
            # Determine if we should use rowid or pk_col
            # If row_id is a number, try rowid first
            use_rowid = str(row_id).isdigit()
            if connection.vendor != 'sqlite':
                use_rowid = False
            
            if use_rowid:
                sql = f'DELETE FROM "{user_table.real_name}" WHERE rowid = %s'
            else:
                # Find primary key column name from schema
                pk_col = 'id' # Default
                for col in user_table.schema:
                    if col.get('pk'):
                        pk_col = col.get('name')
                        break
                sql = f'DELETE FROM "{user_table.real_name}" WHERE "{pk_col}" = %s'
            
            print(f"DEBUG DELETE: Table={user_table.real_name}, UseRowID={use_rowid}, ID={row_id}")
            print(f"DEBUG SQL: {sql}")
            
            with connection.cursor() as cursor:
                cursor.execute(sql, [row_id])
                deleted_count = cursor.rowcount
                print(f"DEBUG RESULT: Deleted {deleted_count} rows")
            
            # If rowid failed but it was a number, maybe it was actually a numeric PK?
            # (Unlikely in SQLite unless WITHOUT ROWID, but safety fallback)
            if deleted_count == 0 and use_rowid:
                 # Find primary key column name just in case
                pk_col = 'id'
                for col in user_table.schema:
                    if col.get('pk'):
                        pk_col = col.get('name')
                        break
                
                # Only retry if PK is not rowid (to avoid loop)
                if pk_col.lower() != 'rowid': 
                     sql_retry = f'DELETE FROM "{user_table.real_name}" WHERE "{pk_col}" = %s'
                     print(f"DEBUG RETRY: {sql_retry}")
                     with connection.cursor() as cursor:
                        cursor.execute(sql_retry, [row_id])
                        deleted_count = cursor.rowcount

            if deleted_count == 0:
                print("WARNING: No rows deleted! Check if ID matches exactly.")
            
            # Log activity
            log_activity(
                user=request.user,
                action='DELETE_ROW',
                table_name=table_name,
                description=f'Deleted row {row_id} from "{table_name}"',
                metadata={'row_id': row_id},
                request=request
            )
            
            return Response({
                'success': True,
                'message': f'Row deleted ({deleted_count} rows affected)'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StatsView(APIView):
    """
    GET: Get dashboard statistics
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta
        
        user = request.user
        total_tables = UserTable.objects.filter(user=user).count()
        
        total_rows = 0
        for table in UserTable.objects.filter(user=user):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table.real_name}"')
                    total_rows += cursor.fetchone()[0]
            except:
                pass
        
        # Count actions from today
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        actions_today = ActivityLog.objects.filter(
            user=user,
            created_at__gte=today_start
        ).count()
        
        return Response({
            'total_tables': total_tables,
            'total_rows': total_rows,
            'database_size': 0,
            'actions_today': actions_today,
        })


class ActivityView(APIView):
    """
    GET: Get activity logs with pagination and filtering
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Query params
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('limit', 25))
        action_filter = request.query_params.get('action', None)
        table_filter = request.query_params.get('table', None)
        
        # Base queryset - user's logs only, ordered by newest first
        logs = ActivityLog.objects.filter(user=user).order_by('-created_at')
        
        # Apply filters
        if action_filter:
            logs = logs.filter(action=action_filter)
        if table_filter:
            logs = logs.filter(table_name__icontains=table_filter)
        
        # Get total before pagination
        total = logs.count()
        
        # Paginate
        offset = (page - 1) * page_size
        logs = logs[offset:offset + page_size]
        
        # Format response
        formatted_logs = []
        for log in logs:
            formatted_logs.append({
                'id': log.id,
                'action': log.action,
                'table_name': log.table_name,
                'description': log.description,
                'metadata': log.metadata,
                'ip_address': log.ip_address,
                'created_at': log.created_at.isoformat(),
                'time_ago': self._get_time_ago(log.created_at),
            })
        
        return Response({
            'logs': formatted_logs,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 0,
        })
    
    def _get_time_ago(self, dt):
        """Convert datetime to human-readable 'time ago' string"""
        from django.utils import timezone
        
        now = timezone.now()
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return 'Just now'
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f'{minutes}m ago'
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f'{hours}h ago'
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f'{days}d ago'
        else:
            return dt.strftime('%b %d, %Y')


# ============================================
# EXPORT / IMPORT VIEWS
# ============================================

class TableExportView(APIView):
    """
    GET: Export table data as JSON or CSV
    Query params: format=json|csv (default: json)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, table_name):
        from django.http import HttpResponse
        from django.utils import timezone
        import json
        import csv
        import io
        
        # Get format
        export_format = request.query_params.get('format', 'json').lower()
        
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            with connection.cursor() as cursor:
                # Get column names
                columns = [col.get('name') for col in user_table.schema]
                
                # Get all rows
                cursor.execute(f'SELECT * FROM "{user_table.real_name}"')
                rows = cursor.fetchall()
                
                # Convert to list of dicts
                rows_data = [dict(zip(columns, row)) for row in rows]
            
            # Log activity
            log_activity(
                user=request.user,
                action='EXPORT_DATA',
                table_name=table_name,
                description=f'Exported {len(rows_data)} rows from "{table_name}" as {export_format.upper()}',
                metadata={'format': export_format, 'row_count': len(rows_data)},
                request=request
            )
            
            if export_format == 'csv':
                # Generate CSV
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows_data)
                
                response = HttpResponse(output.getvalue(), content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{table_name}.csv"'
                return response
            else:
                # Generate JSON
                export_data = {
                    'table_name': table_name,
                    'columns': user_table.schema,
                    'rows': rows_data,
                    'row_count': len(rows_data),
                    'exported_at': timezone.now().isoformat(),
                }
                
                response = HttpResponse(
                    json.dumps(export_data, indent=2, default=str),
                    content_type='application/json'
                )
                response['Content-Disposition'] = f'attachment; filename="{table_name}.json"'
                return response
                
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TableImportView(APIView):
    """
    POST: Import data from JSON or CSV
    Body: { "format": "json"|"csv", "data": [...] }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, table_name):
        import json
        
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        import_format = request.data.get('format', 'json').lower()
        data = request.data.get('data', [])
        
        if not data:
            return Response({
                'error': 'No data provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # For JSON format, data should already be a list
        # For CSV format, frontend should parse it first
        if not isinstance(data, list):
            return Response({
                'error': 'Data must be a list of rows'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            inserted = 0
            errors = []
            
            for i, row in enumerate(data):
                if not isinstance(row, dict):
                    errors.append(f'Row {i}: Not a valid object')
                    continue
                
                try:
                    columns = list(row.keys())
                    values = list(row.values())
                    placeholders = ', '.join(['%s' for _ in values])
                    columns_str = ', '.join([f'"{col}"' for col in columns])
                    
                    sql = f'INSERT INTO "{user_table.real_name}" ({columns_str}) VALUES ({placeholders})'
                    
                    with connection.cursor() as cursor:
                        cursor.execute(sql, values)
                    
                    inserted += 1
                except Exception as e:
                    errors.append(f'Row {i}: {str(e)}')
            
            # Log activity
            log_activity(
                user=request.user,
                action='IMPORT_DATA',
                table_name=table_name,
                description=f'Imported {inserted} rows into "{table_name}" from {import_format.upper()}',
                metadata={'format': import_format, 'imported': inserted, 'errors': len(errors)},
                request=request
            )
            
            return Response({
                'success': True,
                'imported': inserted,
                'errors': errors[:10] if errors else [],  # Return first 10 errors
                'total_errors': len(errors),
            }, status=status.HTTP_201_CREATED if inserted > 0 else status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TableColumnsView(APIView):
    """
    POST: Add a new column
    PUT: Rename a column
    DELETE: Delete a column
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, table_name):
        """Add a new column to the table"""
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        col_name = request.data.get('name', '').strip()
        col_type = request.data.get('type', 'TEXT').upper()
        
        if not col_name:
            return Response({
                'error': 'Column name is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Map types for PostgreSQL
        if connection.vendor != 'sqlite':
            if col_type == 'BLOB':
                col_type = 'BYTEA'
            elif col_type == 'DATETIME':
                col_type = 'TIMESTAMP'
        
        try:
            with connection.cursor() as cursor:
                sql = f'ALTER TABLE "{user_table.real_name}" ADD COLUMN "{col_name}" {col_type}'
                cursor.execute(sql)
            
            # Update stored schema
            schema = user_table.schema or []
            schema.append({
                'name': col_name,
                'type': col_type,
                'pk': False,
                'notnull': False,
                'unique': False,
                'dflt_value': None
            })
            user_table.schema = schema
            user_table.save()
            
            log_activity(
                user=request.user,
                action='ADD_COLUMN',
                table_name=table_name,
                description=f'Added column "{col_name}" ({col_type}) to "{table_name}"',
                metadata={'column': col_name, 'type': col_type},
                request=request
            )
            
            return Response({
                'success': True,
                'message': f'Column "{col_name}" added'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, table_name):
        """Rename a column"""
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        old_name = request.data.get('old_name', '').strip()
        new_name = request.data.get('new_name', '').strip()
        
        if not old_name or not new_name:
            return Response({
                'error': 'Both old_name and new_name are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if old_name == new_name:
            return Response({
                'error': 'New name must be different from old name'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with connection.cursor() as cursor:
                sql = f'ALTER TABLE "{user_table.real_name}" RENAME COLUMN "{old_name}" TO "{new_name}"'
                cursor.execute(sql)
            
            # Update stored schema
            schema = user_table.schema or []
            for col in schema:
                if col.get('name') == old_name:
                    col['name'] = new_name
                    break
            user_table.schema = schema
            user_table.save()
            
            log_activity(
                user=request.user,
                action='RENAME_COLUMN',
                table_name=table_name,
                description=f'Renamed column "{old_name}" to "{new_name}" in "{table_name}"',
                metadata={'old_name': old_name, 'new_name': new_name},
                request=request
            )
            
            return Response({
                'success': True,
                'message': f'Column renamed from "{old_name}" to "{new_name}"'
            })
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, table_name):
        """Delete a column"""
        try:
            user_table = UserTable.objects.get(user=request.user, table_name=table_name)
        except UserTable.DoesNotExist:
            return Response({
                'error': 'Table not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        col_name = request.data.get('name', '').strip()
        
        if not col_name:
            return Response({
                'error': 'Column name is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if this is a primary key column
        for col in user_table.schema or []:
            if col.get('name') == col_name and col.get('pk'):
                return Response({
                    'error': 'Cannot delete primary key column'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with connection.cursor() as cursor:
                sql = f'ALTER TABLE "{user_table.real_name}" DROP COLUMN "{col_name}"'
                cursor.execute(sql)
            
            # Update stored schema
            schema = user_table.schema or []
            schema = [col for col in schema if col.get('name') != col_name]
            user_table.schema = schema
            user_table.save()
            
            log_activity(
                user=request.user,
                action='DELETE_COLUMN',
                table_name=table_name,
                description=f'Deleted column "{col_name}" from "{table_name}"',
                metadata={'column': col_name},
                request=request
            )
            
            return Response({
                'success': True,
                'message': f'Column "{col_name}" deleted'
            })
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

