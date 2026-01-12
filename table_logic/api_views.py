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
        page = int(request.query_params.get('page', 1))
        limit = min(int(request.query_params.get('limit', 25)), 100)  # Max 100
        sort = request.query_params.get('sort', '')
        order = request.query_params.get('order', 'asc').lower()
        offset = (page - 1) * limit
        
        try:
            with connection.cursor() as cursor:
                schema_columns = [col.get('name') for col in user_table.schema]
                
                # Build ORDER BY clause
                order_clause = ""
                if sort and sort in schema_columns:
                    order_direction = "DESC" if order == "desc" else "ASC"
                    order_clause = f'ORDER BY "{sort}" {order_direction}'
                
                # Get total count
                cursor.execute(f'SELECT COUNT(*) FROM "{user_table.real_name}"')
                total = cursor.fetchone()[0]
                
                # Get rows
                rows_sql = f'SELECT *, rowid FROM "{user_table.real_name}" {order_clause} LIMIT {limit} OFFSET {offset}'
                cursor.execute(rows_sql)
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
