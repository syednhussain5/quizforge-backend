from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from .models import User, Badge, UserBadge, Notification


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2', 'role')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = user.role
        token['xp'] = user.xp
        token['level'] = user.level
        return token


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = '__all__'


class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ('badge', 'earned_at')


class UserProfileSerializer(serializers.ModelSerializer):
    badges = UserBadgeSerializer(source='user_badges', many=True, read_only=True)
    accuracy = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'role', 'avatar', 'bio',
            'xp', 'level', 'total_quizzes_taken', 'total_correct_answers',
            'total_questions_answered', 'current_streak', 'longest_streak',
            'last_active_date', 'accuracy', 'badges', 'preferred_difficulty',
            'created_at'
        )
        read_only_fields = (
            'id', 'xp', 'level', 'total_quizzes_taken', 'total_correct_answers',
            'total_questions_answered', 'current_streak', 'longest_streak',
            'last_active_date', 'accuracy', 'created_at'
        )


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'bio', 'avatar', 'preferred_difficulty', 'receive_notifications')


class LeaderboardSerializer(serializers.ModelSerializer):
    accuracy = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ('id', 'username', 'xp', 'level', 'total_quizzes_taken', 'accuracy', 'current_streak', 'avatar')


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
