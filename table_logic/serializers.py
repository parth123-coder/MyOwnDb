from rest_framework import serializers
from .models import UserTable


class UserTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTable
        fields = ['id', 'table_name', 'real_name', 'schema', 'created_at']
        read_only_fields = ['real_name', 'created_at']


class CreateTableSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)
    columns = serializers.ListField(child=serializers.DictField())

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Table name is required")
        if not value.replace('_', '').isalnum():
            raise serializers.ValidationError("Use only letters, numbers, and underscores")
        return value

    def validate_columns(self, value):
        if len(value) == 0:
            raise serializers.ValidationError("At least one column is required")
        for col in value:
            if not col.get('name', '').strip():
                raise serializers.ValidationError("Column name cannot be empty")
        return value


class RowSerializer(serializers.Serializer):
    """Dynamic serializer for table rows"""
    pass
