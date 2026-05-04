from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from .rfq_cleaner import process_rfq_file


@require_http_methods(['GET', 'POST'])
def index(request):
    context = {}
    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            context['error'] = 'Please upload an Excel file.'
            return render(request, 'app/index.html', context)
        try:
            file_content = process_rfq_file(uploaded_file)
            response = HttpResponse(
                file_content,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename=cleaned_rfq.xlsx'
            return response
        except Exception as exc:
            context['error'] = str(exc)
    return render(request, 'app/index.html', context)
