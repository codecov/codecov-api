from rest_framework import generics

from internal_api.owner.serializers import OwnerDetailsSerializer

class OwnerView(generics.RetrieveAPIView):
    serializer_class = OwnerDetailsSerializer

    def get_object(self):
        return self.request.user
