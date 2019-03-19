# -*- coding: utf-8 -*-

import mechanize
import cookielib
from BeautifulSoup import BeautifulSoup
import html2text
import csv # pro exportovani do CSV
from keboola import docker
import datetime
from datetime import date, timedelta # date input

# initialize KBC configuration 
cfg = docker.Config('/data/')
# validate application parameters
parameters = cfg.get_parameters()


# date format checker
def validate(date_text):
    try:
        datetime.datetime.strptime(date_text, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Incorrect data format, should be YYYY-MM-DD")

#initialize scrape_dates vector
scrape_dates={}

#date preset from input parameters. Bud date_preset='Yesteday'/'last_week' nebo vsechny datumy ve stanovenem intervalu
#! parametr 'date_preset' ma prednost.
if parameters.get('Date_preset')=='Yesterday':
	yesterday = date.today() - timedelta(1)
	d1=yesterday
	d2=d1
elif parameters.get('Date_preset')=='last_week':
	d1 = date.today() - timedelta(7)
	d2 = date.today() - timedelta(1)
elif parameters.get('Date_preset')=='last_3_days':
	d1 = date.today() - timedelta(3)
	d2 = date.today() - timedelta(1)	
elif parameters.get('Date_preset')=='last_31_days':
	d1 = date.today() - timedelta(31)
	d2 = date.today() - timedelta(1)	
elif parameters.get('Date_preset')=='last_year':
	d1 = date.today() - timedelta(365)
	d2 = date.today() - timedelta(1)
#customdate	if not preseted
else:
	validate(parameters.get('Date_from'))
	validate(parameters.get('Date_to'))
	d1=datetime.datetime.strptime(parameters.get('Date_from'),'%Y-%m-%d')
	d2=datetime.datetime.strptime(parameters.get('Date_to'),'%Y-%m-%d')
#vypocet timedelty, ktera urcuje delku tahanych dni zpet	
delta = d2 - d1
for i in range(delta.days+1):
	scrape_dates[i]=(d1+timedelta(i)).strftime('%Y-%m-%d')


for i in range(len(scrape_dates)):
	scrape_date=scrape_dates[i]

	# Cisti stringy obsahujici cislo a menu od mezer a rozpada je na dva stringy : hodnotu a menu
	def sanitizeStrings(text) :
	    textSplitted = text.string.rsplit('&',1)
	    firstResultTemp  = textSplitted[0].replace('&nbsp;','') #pro pripad, ze je cislo vetsi nez 999 a cislo je ve formatu 'X XXX'
	    firstResult = float(firstResultTemp.replace(',','.'))
	    secondResult = textSplitted[1]
	    return firstResult, secondResult
	for entity in parameters.get('Entity').keys():
		for login in parameters.get('Entity').get(entity).keys():
		    # Browser
		    br = mechanize.Browser()
		    # Cookie Jar
		    cj = cookielib.LWPCookieJar()
		    br.set_cookiejar(cj)

		    # Browser options
		    br.set_handle_equiv(True)
		    br.set_handle_gzip(True)
		    br.set_handle_redirect(True)
		    br.set_handle_referer(True)
		    br.set_handle_robots(False)
		    br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

		    br.addheaders = [('User-agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'),('Accept','text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')]

		    # The site we will navigate into, handling it's session
		    if entity=='Heureka.cz':
		    	Url_login='https://ucet.heureka.cz/prihlaseni'
		    if entity=='Heureka.sk':
		    	Url_login='https://ucet.heureka.sk/prihlasenie'
		    br.open(Url_login)

		    # View available forms
		    #for f in br.forms():
		    #    print f

		    # Select the second (index one) form (the first form is a search query box)
		    br.select_form(nr=1)

		    # User credentials
		    br.form['email'] = parameters.get('Entity').get(entity).get(login).get('Login')
		    br.form['password'] = parameters.get('Entity').get(entity).get(login).get('Password')
		    # Login
		    br.submit()

		    from lxml import html
		    import requests

		    no_of_shops=len(parameters.get('Entity').get(entity).get(login).get('Shop_name'))

		    for index in range(0,no_of_shops):
		    	if entity=='Heureka.cz':
		    		Url_stats='http://sluzby.heureka.cz/obchody/statistiky/?shop='+parameters.get('Entity').get(entity).get(login).get('Shop_id')[index]+'&from='+scrape_date+'&to='+scrape_date+'&cat=-4'
		        if entity=='Heureka.sk':
		    		Url_stats='http://sluzby.heureka.sk/obchody/statistiky/?shop='+parameters.get('Entity').get(entity).get(login).get('Shop_id')[index]+'&from='+scrape_date+'&to='+scrape_date+'&cat=-4'
		        print "Beginning to extract stats from "+Url_stats
		        shop = parameters.get('Entity').get(entity).get(login).get('Shop_name')[index]
		        page = br.open(Url_stats).read()
		        tree = html.fromstring(page)
		        soup1 = BeautifulSoup(page)
		        tabulka = soup1('table',{'class':'shop-list roi'})
		        rows = BeautifulSoup(str(tabulka)).findChildren(['tr'])


		        L = [] # deklarujeme prazdny list s vysledky
		        for row in rows:
		            cells = row.findChildren('td')
		            cells = cells[0:4] #chceme jen jmeno vyhledavace a prvni tri hodnty
		            if len(cells) >= 4 :
		                # costs cisteni a uprava
		                temp = sanitizeStrings(cells[3])
		                costs = temp[0]
		                currency = temp[1]
		                if currency == u'nbsp;Kč' :
		                    currency = 'CZK'
		                if currency == u'nbsp;€' :
		                    currency = 'EUR'
		                # cpc cisteni a uprava
		                #print(costs)
		                #print(currency)
		                temp = sanitizeStrings(cells[2])
		                cpc = temp[0]

		                # visits cisteni a uprava
		                visits_temp = cells[1].string.replace('&nbsp;','') #pro pripad, ze je cislo vetsi nez 999 a cislo je ve formatu 'X XXX'
		                visits = float(visits_temp)
		                # name cisteni a uprava
		                name = cells[0].string
		                if name == None :
		                    name = entity

		                prvekL = {'shop':shop,
		                        'date':scrape_date,
		                        'name':name,
		                        'visits':visits,
		                        'cpc':cpc,
		                        'costs':costs,
		                        'currency':currency}
		                L.append(prvekL)
		            #for cell in cells:
		            #    value = cell.string
		            #    prvekL.append(value)


		        keys = ['name', 'visits', 'cpc', 'costs', 'currency','shop','date']
		        #csv.register_dialect('singlequote', quotechar="'", quoting=csv.QUOTE_ALL)
		        #csv.register_dialect('escaped', escapechar='\\', doublequote=False, quoting=csv.QUOTE_NONE)

		        with open('/data/out/tables/'+parameters.get('Entity').get(entity).get(login).get('Shop_name')[index]+'.csv', mode='a+', encoding='utf-8') as output_file:
		            dict_writer = csv.DictWriter(output_file, keys, lineterminator= '\n', delimiter=',', quotechar='"')
		            dict_writer.writeheader()
		            dict_writer.writerows(L)
