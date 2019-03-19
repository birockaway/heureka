import csv
import datetime
from datetime import date, timedelta
import pandas as pd
from lxml import html
import time
import mechanicalsoup
from bs4 import BeautifulSoup
from keboola import docker

# this is the way how to store data in config files:
#cfg = docker.Config('data')
cfg = docker.Config('/data/')
parameters = cfg.get_parameters()


# load category ids to scrape
#df = pd.read_csv('in/tables/categories_to_scrape.csv')
#category_ids = df.category_id

# date format checker
def validate(date_text):
	try:
		datetime.datetime.strptime(date_text, '%Y-%m-%d')
	except ValueError:
		raise ValueError("Incorrect data format, should be YYYY-MM-DD")

# initialize scrape_dates dict.
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

# devide scraped results into two columns: Value and currency;
# So I can easy work with Eur or another currency in future.
def sanitizeStrings(text) :
    textSplitted = text.string.rsplit(None,1)
    firstResultTemp  = textSplitted[0].replace(' ','') # if value > 999 and it result would be X XXX
    firstResult = firstResultTemp.replace(',','.')
    secondResult = textSplitted[1]
    return firstResult, secondResult


#yesterday = date.today() - timedelta(1)
#desired_date = date.today() - timedelta(DATE_PERIOD)


#print('Scraping from ' + desired_date.strftime('%Y-%m-%d') + ' to ' + yesterday.strftime('%Y-%m-%d'))

#count days between dates
#delta = yesterday - desired_date

#for i in range(delta.days+1):
#	scrape_dates[i]=(desired_date+timedelta(i)).strftime('%Y-%m-%d')

for i in range(len(scrape_dates)):
  scrape_date=scrape_dates[i]
  print("Started scraping for " +  scrape_date)
  for entity in parameters.get('Entity').keys():
    for login in parameters.get('Entity').get(entity).keys():
      # Create a browser object
      browser = mechanicalsoup.Browser()

      if entity=='Heureka.cz':
        Url_login='https://ucet.heureka.cz/prihlaseni'
      if entity=='Heureka.sk':
        Url_login='https://ucet.heureka.sk/prihlasenie'

      login_page = browser.get(Url_login)

      # grab the login form
      login_form = login_page.soup.find("form", {"class":"c-form c-form--login js-form"})


      login_form.find("input", {"name": "email"})["value"] = parameters.get('Entity').get(entity).get(login).get('Login')
      login_form.find("input", {"name": "password"})["value"] = parameters.get('Entity').get(entity).get(login).get('Password')

      # submit form
      browser.submit(login_form, login_page.url)

      # this is way how to load config from config JSON.
      NO_OF_SHOPS=len(parameters.get('Entity').get(entity).get(login).get('Shop_name'))

      for index in range(0,NO_OF_SHOPS):
        if entity=='Heureka.cz':
          report_url = browser.get('http://sluzby.heureka.cz/obchody/statistiky/?shop='+parameters.get('Entity').get(entity).get(login).get('Shop_id')[index]+'&from='+scrape_date+'&to='+scrape_date)
        if entity=='Heureka.sk':
          report_url = browser.get('http://sluzby.heureka.sk/obchody/statistiky/?shop='+parameters.get('Entity').get(entity).get(login).get('Shop_id')[index]+'&from='+scrape_date+'&to='+scrape_date)

        # placeholder for SK heureka or sometihing simillar
        shop = parameters.get('Entity').get(entity).get(login).get('Shop_name')[index]
        # create BeautifulSoup object
        report_object = report_url.soup
        # create HTML of content table
        tabulka = report_object.find_all('table',{'class':'shop-list roi'})
        # create empty list so it will be easy to append results there.
        L = []
        rows = BeautifulSoup(str(tabulka), features="lxml").findChildren(['tr'])
        for row in rows:
          cells = row.findChildren('td')#define table
          cells = cells[0:4] #Take just first 4 values of table
          # replace HTML chars
          if len(cells) >= 4 :
            temp = sanitizeStrings(cells[3])
            costs = temp[0]
            currency = temp[1]
            if currency == u'nbsp;Kč' :
            	currency = 'CZK'
            if currency == u'nbsp;€' :
            	currency = 'EUR'

            	temp = sanitizeStrings(cells[2])
            cpc = temp[0]
            visits_temp = cells[1].string.replace('\xa0','') #if value > 999 and it result would be 'X XXX'
            visits = float(visits_temp)
            # name cleaning...
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

          keys = ['name', 'visits', 'cpc', 'costs', 'currency','shop','date']
        #print(L)

          with open('/data/out/tables/'+parameters.get('Entity').get(entity).get(login).get('Shop_name')[index]+'.csv', mode='a+', encoding='utf-8') as output_file:
				    dict_writer = csv.DictWriter(output_file, keys, lineterminator= '\n', delimiter=',', quotechar='"')
				    dict_writer.writeheader()
				    dict_writer.writerows(L)
