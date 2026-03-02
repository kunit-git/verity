from rest_framework import serializers

from .models import Matrix, MatrixColumn


class MatrixColumnSerializer(serializers.ModelSerializer):
    seed_item_type_name = serializers.CharField(
        source="seed_item_type.name", read_only=True
    )
    seed_container_title = serializers.CharField(
        source="seed_container.title", read_only=True
    )
    relation_type_name = serializers.CharField(
        source="relation_type.name", read_only=True
    )
    relation_forward_label = serializers.CharField(
        source="relation_type.forward_label", read_only=True
    )
    relation_reverse_label = serializers.CharField(
        source="relation_type.reverse_label", read_only=True
    )

    class Meta:
        model = MatrixColumn
        fields = [
            "id",
            "position",
            "label",
            "seed_item_type",
            "seed_item_type_name",
            "seed_container",
            "seed_container_title",
            "relation_type",
            "relation_type_name",
            "relation_forward_label",
            "relation_reverse_label",
            "direction",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        # Merge with instance values for partial updates
        position = data.get("position", getattr(self.instance, "position", None))
        seed_item_type = data.get(
            "seed_item_type", getattr(self.instance, "seed_item_type", None)
        )
        relation_type = data.get(
            "relation_type", getattr(self.instance, "relation_type", None)
        )
        direction = data.get(
            "direction", getattr(self.instance, "direction", None)
        )

        if position == 0:
            if not seed_item_type:
                raise serializers.ValidationError(
                    "Column 0 (seed) must specify seed_item_type."
                )
            if relation_type or direction:
                raise serializers.ValidationError(
                    "Column 0 (seed) must not specify relation_type or direction."
                )
        else:
            if not relation_type:
                raise serializers.ValidationError(
                    "Traversal columns (position > 0) must specify relation_type."
                )
            if not direction:
                raise serializers.ValidationError(
                    "Traversal columns (position > 0) must specify direction."
                )
        return data


class MatrixSerializer(serializers.ModelSerializer):
    columns = MatrixColumnSerializer(many=True, read_only=True)
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = Matrix
        fields = [
            "id",
            "name",
            "description",
            "created_by",
            "created_by_username",
            "columns",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class MatrixWriteSerializer(serializers.ModelSerializer):
    columns = MatrixColumnSerializer(many=True)

    class Meta:
        model = Matrix
        fields = ["id", "name", "description", "columns"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        columns_data = validated_data.pop("columns")
        validated_data["created_by"] = self.context["request"].user
        matrix = Matrix.objects.create(**validated_data)
        for col_data in columns_data:
            MatrixColumn.objects.create(matrix=matrix, **col_data)
        return matrix

    def update(self, instance, validated_data):
        columns_data = validated_data.pop("columns", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if columns_data is not None:
            instance.columns.all().delete()
            for col_data in columns_data:
                MatrixColumn.objects.create(matrix=instance, **col_data)
        return instance

    def to_representation(self, instance):
        return MatrixSerializer(instance, context=self.context).to_representation(
            instance
        )
