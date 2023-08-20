from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from .models import LLM, Prompt, Responses
from .permissions import IsOwnerOrReadOnly
from .serializers import LLMSerializer, PromptSerializer, ResponsesSerializer

from rest_framework import status
import requests
import json

import environ
env =environ.Env()
environ.Env.read_env()

API_TOKEN= env("API_TOKEN", default=None)

if not API_TOKEN:
    raise ValueError("API_TOKEN is not set in .env file.")

HEADERS ={"Authorization": f"Bearer {API_TOKEN}"}
BASE_API_URL = "https://api-inference.hugglingface.co/models/"

def make_api_call(api_code,query):
    #construct the complete API URL using the model's api_code
    api_url = f"{BASE_API_URL}{api_code}"
    #build the payload per docs
    payload = {
        "inputs": query
    }

    #make the api request
    response = requests.post(api_url, headers=HEADERS, json=payload)

    #error handling
    if response.status_code != 200:
        raise ValueError(f"API call failed with status code {response.status_code}: {response.text}")
    return response.json()


# lists and creates prompts
class PromptList(ListCreateAPIView):
    permission_classes = (IsOwnerOrReadOnly,)
    serializer_class = PromptSerializer

    def get_queryset(self):
        user = self.request.user
        return Prompt.objects.filter(user_id=user)

    def create(self, request, *args, **kwargs):
        #creates the prompt
        response = super(PromptList,self).create(request, *args, **kwargs)

        #if prompt successful
        if response.status_code == status.HTTP_201_CREATED:
            prompt = self.object
            for model_id in prompt.lang_models:
                lang_model = LLM.objects.get(pk=model_id)
                #use prompt.input_str as the query to be sent to the api
                api_response = make_api_call(lang_model.api_code, prompt.input_str)

                #save the response
                #api_response['generated_text'] per the actual structure of huggingface
                Responses.objects.create(prompt_id=prompt, lang_model_id=lang_model, response=api_response['generated_text'])

        return response

#allows user to edit individual responses
class PromptDetail(RetrieveUpdateDestroyAPIView):
    permission_classes = (IsOwnerOrReadOnly,)
    serializer_class = PromptSerializer

    def get_queryset(self):
        user = self.request.user
        return Prompt.objects.filter(user_id=user)


class ResponseList(ListAPIView):  # lists responses specifc to a single prompt
    permission_classes = (IsOwnerOrReadOnly,)
    serializer_class = ResponsesSerializer

    def get_queryset(self):
        user = self.request.user
        prompt_pk = self.kwargs['pk']
        return Responses.objects.filter(prompt_id__user_id=user, prompt_id=prompt_pk)


class LLMList(ListAPIView):
    queryset = LLM.objects.all()
    serializer_class = LLMSerializer
