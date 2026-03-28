# api/serializers.py

from rest_framework import serializers
from core.models import PREntry, UserModel, Session, Polygon
import json


class LoginSerializer(serializers.Serializer):
    employee_id = serializers.CharField(required=True, help_text="Employee ID or Email")
    password_new = serializers.CharField(required=True, help_text="User password", write_only=True)


class VersionCheckSerializer(serializers.Serializer):
    version = serializers.IntegerField(required=True, help_text="App version number")


class PropertyOwnerSerializer(serializers.ModelSerializer):
    """Serializer for property owner entries"""
    
    class Meta:
        model = PREntry
        fields = [
            'id', 'session', 'entry_index', 'mode', 'data', 
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_data(self, value):
        """Validate the data structure for property owner"""
        required_fields = ['owner_name', 'owner_phone', 'property_address']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"{field} is required")
        return value


class PropertyPOCSerializer(serializers.ModelSerializer):
    """Serializer for property person of contact entries"""
    
    class Meta:
        model = PREntry
        fields = [
            'id', 'session', 'entry_index', 'mode', 'data', 
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_data(self, value):
        """Validate the data structure for property POC"""
        required_fields = ['poc_name', 'poc_phone', 'relationship']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"{field} is required")
        return value


class PassPropertySerializer(serializers.ModelSerializer):
    """Serializer for passed property entries"""
    
    class Meta:
        model = PREntry
        fields = [
            'id', 'session', 'entry_index', 'mode', 'data', 
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_data(self, value):
        """Validate the data structure for passed property"""
        if 'reason' not in value:
            raise serializers.ValidationError("reason is required")
        return value


class NoPropertyContactSerializer(serializers.ModelSerializer):
    """Serializer for no-contact property entries"""
    
    class Meta:
        model = PREntry
        fields = [
            'id', 'session', 'entry_index', 'mode', 'data', 
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_data(self, value):
        """Validate the data structure for no-contact"""
        if 'reason' not in value:
            raise serializers.ValidationError("reason is required")
        return value