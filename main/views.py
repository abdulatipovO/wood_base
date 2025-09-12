from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.views import View
from django.http import JsonResponse
from .models import *
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from datetime import datetime, date , timedelta
from .others_func import calc_end_write,container_info
from django.utils import timezone

from .decorator_handle import check_active_user_view


class HomeView(LoginRequiredMixin,View):
    
    def get(self, request):
        
        containers = Container.objects.filter(status=True,  is_active=True).order_by('-id')
        all_product_size = ProductSize.objects.filter(status=True)
        suppliers = Supplier.objects.filter(is_active=True)
        
        
        context = {
            "containers":containers,
            "all_product_size":all_product_size,
            "suppliers":suppliers,
        }
        
        return render(request, 'index.html',context)

    @check_active_user_view
    def post(self, request):
        
        supplier_id = int(request.POST['supplier'])
        container_name = request.POST['container_name']
        come_date = datetime.strptime(request.POST['come_date'], "%Y-%m-%d").date()
        
        supplier = Supplier.objects.filter(id=supplier_id).first()
        
        
        container = Container.objects.create(supplier_container=supplier, name=container_name, come_date=come_date)
        
        pk = container.id
     
        
        return redirect(f'/container-products-detail/{pk}')
    
# mahsulotlar ro'yxati
class HomeProductView(LoginRequiredMixin, View):

    def get(self, request):
        search = request.GET.get('search')
        start = request.GET.get('start') if request.GET.get('start') else datetime.now().date().replace(day=1)
        end = request.GET.get('end') if request.GET.get('end') else datetime.now().date()
        products = Product.objects.filter(product_container__is_active=True).order_by('-product_container__come_date')
        if search:
            products = products.filter(product_size__product_size_name__icontains=search)
        if start and end:
            products = products.filter(product_container__come_date__gte=start, product_container__come_date__lte=end)


        # Har bir mahsulot uchun sotilgan dona, kub va summani hisoblash
        products_with_sales = []
        for product in products:
            orderitems = OrderItem.objects.filter(product_item=product)
            sold_qty = orderitems.aggregate(total=models.Sum('amount_sold'))['total'] or 0
            sold_cube = 0
            sold_uzs = 0
            sold_usd = 0
            for item in orderitems:
                sold_cube += item.item_cube
                if item.order_item.currency == 1:
                    sold_usd += item.total_price
                else:
                    sold_uzs += item.total_price
            products_with_sales.append({
                'product': product,
                'sold_qty': sold_qty,
                'sold_cube': sold_cube,
                'sold_uzs': sold_uzs,
                'sold_usd': sold_usd
            })

        context = {
            'products_with_sales': products_with_sales,
            'search_value': search,
            'start_value': start,
            'end_value': end,
        }
        return render(request, 'products_index.html', context)

class SellProductsView(LoginRequiredMixin, View):
    def get(self, request):
        search = request.GET.get('search')
        start = request.GET.get('start')
        end = request.GET.get('end')
        # Use select_related for related fields and only to limit columns
        products = Product.objects.select_related('product_container', 'product_size') \
            .filter(product_container__is_active=True) \
            .only('id', 'rest_cube', 'rest_qty', 'product_container__id', 'product_container__come_date', 'product_container__name', 'product_size__product_size_name', 'product_size__product_size_title') \
            .order_by('-product_container__come_date')
        if search:
            products = products.filter(product_size__product_size_name__icontains=search)
        if start and end:
            products = products.filter(product_container__come_date__gte=start, product_container__come_date__lte=end)

        context = {
            'products': products,
            'start_value': start,
            'end_value': end,
        }
        return render(request, 'select_products.html', context)
    
    def post(self, request):
        type = request.GET.get('type')
        if type == 'add':
            product = Product.objects.get(id=request.POST.get('product_id'))
            count = request.POST.get('count')
            price = request.POST.get('price')
            basket, c = Basket.objects.get_or_create(product=product)
            basket.count = float(count)
            basket.price = float(price)
            basket.save()
        return JsonResponse({'success': True})

import json

class BasketListView(LoginRequiredMixin, View):
    def get(self, request):
        baskets = Basket.objects.all()
        clients = Client.objects.filter(is_active=True)
        return render(request, 'basket.html', {
            'baskets': baskets,
            'clients': clients
        })
    
    def post(self, request):
        data = json.loads(request.body)
        baskets = data.get('baskets', [])
        client_id = data.get('client')
        currency = data.get('currency')
        rate = data.get('rate')
        amount = data.get('amount')
        is_credit = data.get('isCredit', None)

        if baskets == []:
            return JsonResponse({
                'message': 'Savat bo\'sh'
            }, status=400)
        
        if not rate or not amount:
            return JsonResponse({
                'message': 'Kurs va Umumiy summani kiriting!'
            }, status=400)
        
        # Basketlarni product_container bo'yicha guruhlash
        from collections import defaultdict
        grouped = defaultdict(list)
        for b in baskets:
            basket_obj = Basket.objects.get(id=b['id'])
            # Basketni update qilish
            basket_obj.count = b['count']
            basket_obj.price = b['price']
            basket_obj.save()
            product = basket_obj.product
            container_id = product.product_container_id
            grouped[container_id].append((b, product))

        client = Client.objects.filter(id=client_id).first() if client_id else None

        created_orders = []
        for container_id, items in grouped.items():
            container = Container.objects.get(id=container_id)
            order = Order.objects.create(
                container_order=container,
                customer=client,
                currency=1 if currency == 'USD' else 2,
                sale_exchange_rate=int(rate) or 0,
                discount=0,
                debt_status=is_credit
            )
            for b, product in items:
                item = OrderItem.objects.create(
                    order_item=order,
                    product_item=product,
                    amount_sold=float(b['count']),
                    product_cost=float(b['price']),
                )
                product.rest_qty -= item.amount_sold
                product.rest_cube -= item.item_cube
                product.save()

            if client != None and is_credit == True:
                client_account, created = ClientAccount.objects.get_or_create(
                    container_client=container,
                    client_info=client,
                )
                if order.currency == 1:
                    client_account.debt_usd -= float(order.total_items_price)
                else:
                    client_account.debt_uzs -= float(order.total_items_price)
                client_account.save()
            
            elif client != None and is_credit == False:
                if order.currency == 1:
                    container.paid_amount += float(order.total_items_price)
                if order.currency == 2:
                    container.paid_amount += (float(order.total_items_price) / order.sale_exchange_rate)

            elif client == None and is_credit == False:
                if order.currency == 1:
                    container.paid_amount += float(order.tot)
                if order.currency == 2:
                    container.paid_amount += (float(order.tot) / order.sale_exchange_rate)

            else:
                return JsonResponse({
                    'message': 'Nasiyaga savdo qilinganda mijoz tanlanishi shart!'
                }, status=400)
            
            container.save()
            created_orders.append(order.id)
            
            # order.discount = sum([i.total_price for i in OrderItem.objects.filter(order_item=order)]) - float(amount)
            order.save()
        # Hammasi muvaffaqiyatli bo'lsa, barcha basketlarni o'chirish
        Basket.objects.all().delete()
        messages.success(request, 'Savatchadagi mahsulotlar sotildi!')
        return JsonResponse({'success': True})

def delete_basket(request, id):
    if id != 0:
        Basket.objects.get(id=id).delete()
        messages.success(request, 'Savatdagi mahsulot o\'chirildi!')
    else:
        Basket.objects.all().delete()
        messages.success(request, 'Savat tozalandi!')
    return redirect(request.META['HTTP_REFERER'])
    

class ContainerProductsDetailView(LoginRequiredMixin,View):
    
    def get(self, request, pk):
       
        context = container_info(request, pk)
        context['products'] = Product.objects.filter(product_container=context['container'], is_active=True)
        
      
        
        return render(request, 'container-products-detail.html', context)
    
    @check_active_user_view
    def post(self, request, pk):
        
        if int(request.POST['select_size']) > 0:
            calc_wood = calc_end_write(request,pk)
            
        else:
            print("error select tanlash kere")
        
        
        return  redirect(f'/container-products-detail/{pk}')
    
    
class ContainerTradeDetailView(LoginRequiredMixin,View):
    
    def get(self, request,pk):
        product_list = []
        context = container_info(request, pk)
        products = Product.objects.filter(product_container=context['container'], is_active=True)
        
        for p in products:
            if p.rest_qty > 0:
                product_list.append(p)
  
        clients = Client.objects.all()
     
        
        context["clients"] = clients
        context["product_list"] = product_list
        
        return render(request, 'container-trade-detail.html', context)
    
    
class ContainerExpenceDetailView(LoginRequiredMixin,View):
    def get(self, request, pk):
        
        context = container_info(request, pk)
        
        return render(request, 'container-expence-detail.html',context)
    


class ContainerTradeHistoryView(View):
    def get(self, request,pk):
       
        
        context = container_info(request, pk)
        
        container = Container.objects.filter(id=int(pk)).first()
        orders = Order.objects.filter(container_order=container, is_active=True).order_by('-id')
        
        context["orders"] = orders
        
        
        return render(request, 'container-trade-history.html',context)
    

class ContainerDeleteView(View):
    def post(self, request):
        
        container_id = int(request.POST['container_id'])
        container = Container.objects.filter(id=container_id).first()
        container.is_active = False
        container.save()
        
        return redirect('/')


class Clientiew(LoginRequiredMixin,View):
    def get(self, request):
        clients = Client.objects.filter(is_active=True).order_by('-id')
        context = {
            "clients":clients
        }
        return render(request, 'clients.html',context)
    
    @check_active_user_view
    def post(self,request):
        name = request.POST['name']
        phone = request.POST['phone']
        
        Client.objects.create(name=name,phone=phone)
        
        
        return redirect('/clients')

    
class PaymentView(LoginRequiredMixin,View):
    def get(self, request):
        start_date = request.GET.get('start-date') if request.GET.get('start-date') else (datetime.now().date() - timedelta(days=31)).strftime('%Y-%m-%d')
        end_date = request.GET.get('end-date') if request.GET.get('end-date') else datetime.now().date().strftime('%Y-%m-%d')
        clients = Client.objects.all()
        containers = Container.objects.filter(status=True,  is_active=True)
        payments = Payment.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date).order_by('-id')
        
        
        context = {
            "clients":clients,
            "containers":containers,
            "payments":payments,
            "start_date":start_date,
            "end_date":end_date,
        }
        return render(request, 'payments.html', context )
    
    
class GeneralExpence(LoginRequiredMixin,View):
    def get(self, request):
        
        expense_types = ExpenseType.objects.filter(is_active=True)
        workers = Worker.objects.filter(is_active=True)
        containers = Container.objects.filter(status=True,  is_active=True)
        
        context = {
            "expense_types":expense_types,
            "workers":workers,
            "containers":containers
        }
        
        return render(request, 'general-expenses.html', context)
    
    
class AllExpense(LoginRequiredMixin,View):
    def get(self, request):
        
        expenses = Expense.objects.filter(is_active=True).order_by('-id')
        
        context = {
            "expenses":expenses,
        }
        
        return render(request, 'all_expenses.html', context)
    
    
class WorkerView(LoginRequiredMixin,View):
    def get(self, request):
        
        workers = Worker.objects.filter(is_active=True)
        
        context = {
            "workers":workers
        }
        
        return render(request, 'workers.html', context)
    
    @check_active_user_view
    def post(self,request):
        name = request.POST['name']
        phone = request.POST['phone']
        birth_date = request.POST['birth_date']
        
        
        worker = Worker.objects.create(
            name=name,
            phone=phone,
            birth_date=birth_date
            )
        
        return redirect('/workers')
        
    
    
    
class ArchiveContainers(LoginRequiredMixin,View):
    def get(self,request):
        
        containers = Container.objects.filter(status=False,  is_active=True).order_by('-id')
        
        context = {
            "containers":containers
        }
        return render(request, 'archive-containers.html', context)
    
    
class ArchiveContainerDetail(LoginRequiredMixin,View):
    def get(self,request, pk):
        
        context = container_info(request,pk)
        
        orders = Order.objects.filter(container_order=context['container'], is_active=True).order_by('-id')
        
    
        
        return render(request, 'archive-container-products-detail.html', context)
    
    
class ArchiveContainerExpenseDetail(LoginRequiredMixin,View):
    def get(self, request, pk):
        
        context = container_info(request,pk)
        
       
        return render(request, 'archive-expence-history-detail.html',context)
    
    
class ArchiveContainerTradeDetail(LoginRequiredMixin,View):
      def get(self, request,pk):
        
        context = container_info(request,pk)    

        orders = Order.objects.filter(container_order=context['container'], is_active=True).order_by('-id')
        
        context['orders'] = orders
        
        return render(request, 'archive-trade-history.html',context)
    
    
class BackMainContainer(View):
    def post(self,request):
        container_id = int(request.POST['container_id'])
        
        container = Container.objects.filter(id=container_id).first()
        container.status = True
        container.save()
        
        return redirect('/')
    
    
class BackArchiveContainer(View):
    
    def post(self,request):
        container_id = int(request.POST['container_id'])
        
        container = Container.objects.filter(id=container_id).first()
        container.status = False
        container.save()
        
        return redirect('/trade-history')
        
        
    
    
class NoteView(LoginRequiredMixin,View):
    def get(self, request):
        
        notes = Note.objects.all().order_by('-is_active')
        context = {
            'notes':notes
        }
        return render(request, 'notes.html',context)
    
    
    

class TrashView(View):
    def get(self, request):
        
        thirty_days_ago = timezone.now() - timedelta(days=30)

        old_products = Product.objects.filter(is_active=False, updated_at__lte=thirty_days_ago)
        old_orders = Order.objects.filter(is_active=False, updated_at__lte=thirty_days_ago)
        old_expenses = Expense.objects.filter(is_active=False, updated_at__lte=thirty_days_ago)

        old_products.delete()
        old_orders.delete()
        old_expenses.delete()
        
        products = Product.objects.filter(is_active=False)
        orders = Order.objects.filter(is_active=False)
        expenses = Expense.objects.filter(is_active=False)
        
        context = {
            "products":products,
            "orders":orders,
            "expenses":expenses,
        }
        
        return render(request, 'trash.html', context)
    
    
class SupplierView(View):
    def get(self,request):
        
        suppliers = Supplier.objects.filter(is_active=True)
        
        for supplier in suppliers:
            supplier.calc_all_containers()
            
        containers = Container.objects.filter(is_active=True)
        
        
        context = {
            "suppliers":suppliers,
            "containers":containers
        }
        
        return render(request, 'suppliers.html',context)
    
    def post(self, request):
        name = request.POST['name']
        phone = request.POST['phone']
        
        Supplier.objects.create(name=name, phone=phone)
        
        
        return redirect('/suppliers')
    


class EditSupplier(View):
    def post(self, request):
        supplier_id = int(request.POST['supplier_id'])
        name = request.POST['name']
        phone = request.POST['phone']
        
        supplier = Supplier.objects.filter(id=supplier_id).first()
        supplier.name = name
        supplier.phone = phone
        supplier.save()

        
        return redirect('/suppliers')

class SupplierDetail(View):
    def get(self, request,pk):
        
        supplier = Supplier.objects.filter(id=pk).first()
        containers = supplier.containers.filter(is_active=True)
        
        context  = { 
            "supplier":supplier,
            "containers":containers       
        }
        
        return render(request, 'supplier-detail.html',context)


class SupplierPaymentView(View):
    def get(self, request):
        start_date = request.GET.get('start-date') if request.GET.get('start-date') else (datetime.now().date() - timedelta(days=31)).strftime('%Y-%m-%d')
        end_date = request.GET.get('end-date') if request.GET.get('end-date') else datetime.now().date().strftime('%Y-%m-%d')
        payments = PaymentToSupplier.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
        suppliers = Supplier.objects.filter(is_active=True)
        
        context = {
            'payments': payments,
            'suppliers': suppliers,
            'start_date': start_date,
            'end_date': end_date
        }
        return render(request, 'supp_payments.html', context)


class StatisticsView(LoginRequiredMixin, View):

    def get(self, request):
        start_date = request.GET.get('start_date', date.today().replace(day=1, month=1).strftime('%Y-%m-%d'))
        end_date = request.GET.get('end_date', date.today().strftime('%Y-%m-%d'))
        expenses = Expense.objects \
        .filter(created_at__date__gte=start_date, created_at__date__lte=end_date) \
        .defer('expense_type', 'workers').prefetch_related(None)

        payments = Payment.objects \
        .filter(created_at__date__gte=start_date, created_at__date__lte=end_date) \
        .defer('client_account').prefetch_related(None)

        containers = round(sum([con.total_products_summa for con in Container.objects
        .filter(come_date__gte=start_date, come_date__lte=end_date)
        .defer('supplier_container')]), 2)
        
        expenses_uzs = round(sum([exp.expense_summa for exp in expenses.filter(currency=2)]), 2)

        expenses_usd = round(sum([exp.expense_summa for exp in expenses.filter(currency=1)]), 2)

        payment_uzs = round(sum([pay.payment_amount for pay in payments.filter(currency=2)]), 2)

        payment_usd = round(sum([pay.payment_amount for pay in payments.filter(currency=1)]), 2)

        order_total_usd = round(sum([ord.total_summa for ord in Order.objects
        .filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
        .defer('container_order', 'customer').prefetch_related(None)]), 2)

        expenses_usd_only = round(sum([exp.sum_to_dollar for exp in expenses]), 2)

        payment_usd_only = round(sum([pay.uzs_to_usd for pay in payments]), 2)

        # success = containers - (expenses_usd_only + payment_usd_only)
        full_success = round(order_total_usd - (expenses_usd_only + payment_usd_only), 2)
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'containers': containers,
            'expenses_uzs': expenses_uzs,
            'expenses_usd': expenses_usd,
            'payment_uzs': payment_uzs,
            'payment_usd': payment_usd,
            'order_total_usd': order_total_usd,
            'success': full_success,
        }
        return render(request, 'statistics.html', context)

class UsersView(LoginRequiredMixin,View):
    def get(self, request):
        
        users = CustomUser.objects.all()
        
        context = {
            "users":users
        }
        
        return render(request, 'users.html', context)
    
    



def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')  # Redirect to a home page or dashboard
        else:
            messages.error(request, "Login yoki parol notog'ri")
            return render(request, 'auth-login.html', {'error': 'Invalid credentials'})
    return render(request, 'auth-login.html')

def logout_view(request):
    logout(request)
    return redirect('/login')


def handler_404(request, exception):
    return render(request, 'error-404.html')

def handler_500(request):
    return render(request, 'error-500.html')

# for i in ProductSize.objects.all():
#     print(i.product_size_name)
#     i.change_name()
#     print(i.product_size_name)


def client_delete(request, id):
    client = Client.objects.get(id=id)
    client.is_active = False
    client.save()
    return redirect(request.META['HTTP_REFERER'])

def client_add_popup(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        if name and phone:
            Client.objects.create(name=name, phone=phone)
            return JsonResponse({'success': True, 'message': 'Mijoz qo\'shildi!'})
        else:
            return JsonResponse({'success': False, 'message': 'Iltimos, barcha maydonlarni to\'ldiring!'})
    return render(request, 'popup/client_add.html')